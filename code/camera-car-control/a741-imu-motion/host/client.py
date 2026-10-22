"""Single-owner UDP control client. Motion commands are never retried."""
import math
from pathlib import Path
import socket
import struct
import sys
import time
import threading
import ipaddress
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host"))
from legacy import FrameParser, frame
from protocol import crc16_ccitt, decode_status
from heading_control import HeadingPD


@dataclass
class Diagnostics:
    request_id: int = 0
    requests: int = 0
    replies: int = 0
    timeouts: int = 0
    discarded: int = 0
    rtt_ms: float = 0
    last_command: int = 0
    last_received_bytes: int = 0
    last_discard_reason: str = ""
    retries: int = 0


class CalibrationRejected(RuntimeError):
    """A calibration precondition failed; the connection can remain available."""


class HoldLease:
    """The UI must renew the deadman lease; a stuck UI cannot drive forever."""
    def __init__(self, timeout=.2):
        self.event = threading.Event()
        self.timeout = timeout
        self.deadline = 0

    def set(self):
        self.deadline = time.monotonic()+self.timeout
        self.event.set()

    def clear(self):
        self.event.clear()

    def is_set(self):
        return self.event.is_set() and time.monotonic() < self.deadline

    def renew(self):
        if self.is_set():
            self.deadline = time.monotonic()+self.timeout


class Client:
    def __init__(self, peer="192.168.0.2", local_port=5001, timeout=.12):
        self.peer = (str(ipaddress.IPv4Address(peer)), 5000)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", local_port))
        self.socket.settimeout(timeout)
        self.session = __import__("secrets").randbits(32)
        self.seq = 0
        self.diag = Diagnostics()
        self.timeout = timeout
        self.sensor_pins_enabled = False
        self.imu_test = False
        self.motion_lidar = False

    def command(self, kind, payload=b"", reply=0x80):
        if getattr(self,"sensors_only",False) and kind in (2,0x11,0x42,0x45,0x47):
            raise ValueError("传感器调试模式禁止ARM、轮速和旋转指令")
        self.diag.request_id = (self.diag.request_id+1) & 0xffffffff
        self.diag.last_command=kind
        self.diag.last_received_bytes=0
        self.diag.last_discard_reason=""
        self.seq = (self.seq+1) & 255
        body = struct.pack("<4sII", b"EMC1", self.session, self.diag.request_id)
        body += frame(kind, payload, self.seq, 250)
        start = time.monotonic()
        self.socket.sendto(body + struct.pack("<H", crc16_ccitt(body)), self.peer)
        self.diag.requests += 1
        if reply is None:
            # The bridge serializes commands at 115200 baud; avoid flooding its
            # single request slot with a second datagram before it finishes.
            time.sleep(.004)
            return None
        deadline = start + self.timeout
        try:
            while time.monotonic() < deadline:
                self.socket.settimeout(max(.001, deadline-time.monotonic()))
                data, source = self.socket.recvfrom(2048)
                self.diag.last_received_bytes=len(data)
                if source != self.peer or len(data) < 24:
                    self.diag.last_discard_reason="回复来源或长度不匹配"
                    self.diag.discarded += 1
                    continue
                header = struct.unpack_from("<4sII", data)
                if header != (b"EMC1", self.session, self.diag.request_id) or crc16_ccitt(data[:-2]) != int.from_bytes(data[-2:], "little"):
                    self.diag.last_discard_reason="EMC1会话/请求序号/CRC不匹配"
                    self.diag.discarded += 1
                    continue
                parsed = FrameParser().feed(data[12:-2])
                if len(parsed) != 1 or parsed[0][:2] != (reply, self.seq):
                    self.diag.last_discard_reason="内部协议回复类型/序号/CRC不匹配"
                    self.diag.discarded += 1
                    continue
                self.diag.replies += 1
                self.diag.rtt_ms = (time.monotonic()-start)*1000
                return parsed[0][2]
        except socket.timeout:
            pass
        self.diag.timeouts += 1
        detail=self.diag.last_discard_reason or "未收到控制回复"
        raise TimeoutError(f"UDP 控制请求 {self.diag.request_id} 超时（命令0x{kind:02X}，{detail}）；动作已取消")

    def stop(self):
        return decode_status(self.command_idempotent(4))

    def command_idempotent(self, kind, payload=b"", reply=0x80):
        """Retry only bounded, explicitly repeatable stop/config/status requests."""
        if kind not in (4,0x20,0x30,0x40,0x41,0x44):
            raise ValueError("该命令不允许自动重试")
        for attempt in range(2):
            try:
                return self.command(kind,payload,reply)
            except TimeoutError:
                if attempt:
                    raise
                self.diag.retries+=1

    def disarm(self):
        return decode_status(self.command(3))

    def connect(self, calibration):
        # STOP is the only command allowed to establish a new EMC1 session.
        self.stop()
        cap = self.command_idempotent(0x40, reply=0xc0)
        if len(cap) != 8 or cap[:4] != b"EVM1" or not struct.unpack_from("<H", cap, 4)[0] & 0x10:
            raise ValueError("需要 A741 固件能力；当前固件不支持此控制接口")
        self.sensor_pins_enabled = bool(struct.unpack_from("<H", cap, 4)[0] & 0x20)
        self.imu_test = struct.unpack_from("<H", cap, 4)[0] & 0xc0 == 0xc0
        self.motion_lidar = struct.unpack_from("<H", cap, 4)[0] & 0x300 == 0x300
        self.imu_motion = bool(struct.unpack_from("<H", cap, 4)[0] & 0x400)
        model = self.command_idempotent(0x44, struct.pack("<I", 12), reply=0xc4)
        if len(model) != 12 or struct.unpack_from("<I", model, 4)[0] != 6050:
            raise ValueError("当前 FPGA 不是 MPU6050 构建，不能沿用 JY901 诊断位流")
        values = calibration.values(require_track=False)
        for key, value in enumerate(values):
            if value is None:
                continue
            self.command_idempotent(0x30, struct.pack("<BI", key, value))
            actual = self.command_idempotent(0x44, struct.pack("<I", key), reply=0xc4)
            if len(actual) != 12 or struct.unpack_from("<II", actual) != (key, value):
                raise ValueError(f"FPGA 参数 {key} 核对失败")
        return self.status()

    def status(self):
        return decode_status(self.command_idempotent(0x20))

    def sensors(self):
        p = self.command_idempotent(0x41, reply=0xc1)
        if len(p) != 32 or p[0] != 1:
            raise ValueError("A741 sensor reply schema mismatch")
        return {"flags": p[1], "valid": p[2], "calibration": p[3],
                "yaw": struct.unpack_from("<h", p, 4)[0],
                "gyro": struct.unpack_from("<h", p, 6)[0],
                "tof": struct.unpack_from("<H", p, 8)[0],
                "faults": struct.unpack_from("<H", p, 10)[0],
                "ms": struct.unpack_from("<I", p, 12)[0],
                "relative": struct.unpack_from("<i", p, 16)[0],
                "revision": struct.unpack_from("<I", p, 20)[0]}

    def imu_diagnostics(self):
        if not self.imu_test and not getattr(self, "motion_lidar", False):
            raise ValueError("需要新的 MPU6050 测试固件；当前固件不提供该诊断接口")
        values = []
        for key in range(14, 21):
            p = self.command_idempotent(0x44, struct.pack("<I", key), reply=0xc4)
            if len(p) != 12 or struct.unpack_from("<I", p)[0] != key:
                raise ValueError("MPU6050 诊断回复不匹配")
            values.append(struct.unpack_from("<I", p, 4)[0])
        word, errors, sequence = values[:3]
        raw = struct.unpack("<hhhhhh", struct.pack("<III", *values[3:6]))
        temperature = struct.unpack("<h", struct.pack("<H", values[6] & 0xffff))[0]
        identity = (word >> 8) & 255
        model = {0x68: "MPU6050", 0x70: "MPU6500"}.get(identity, "unknown")
        valid = bool(word & (1 << 26))
        temperature_c = temperature/333.87+21 if identity == 0x70 else temperature/340+36.53
        return {"address": word & 0x7f, "who_am_i": (word >> 8) & 255,
                "address_hex": f"0x{word & 0x7f:02X}", "who_am_i_hex": f"0x{identity:02X}", "sensor_model": model,
                "fault": (word >> 16) & 255, "ready": bool(word & (1 << 24)),
                "flat_install": bool(word & (1 << 25)), "sample_valid": bool(word & (1 << 26)),
                "errors": errors, "sample_sequence": sequence,
                "accel_g": [v/16384 for v in raw[:3]] if valid else None,
                "gyro_dps": [v/16.4 for v in raw[3:]] if valid else None,
                "temperature_c": temperature_c if valid else None}

    def wheels(self, left, right, hold=False):
        self.command(0x45 if hold else 0x11, struct.pack("<ii", left, right), reply=None)

    def heartbeat(self):
        self.command(5, reply=None)

    def arm(self, calibration):
        if self.imu_test:
            raise ValueError("当前为陀螺仪测试固件，电机在硬件中锁定")
        if getattr(self, "motion_lidar", False):
            calibration.values()
            if calibration.data.get("motion_user_authorized") is not True:
                raise ValueError("当前配置未记录电机启用授权")
        else:
            calibration.require_hardware()
        if not self.sensor_pins_enabled and not getattr(self, "motion_lidar", False):
            raise ValueError("当前是 P4 禁用的诊断位流，不能运行电机")
        s = decode_status(self.command(2))
        if s.state != 1 or s.faults:
            if s.faults & 0x0004:
                raise CalibrationRejected(
                    "FPGA 已锁存编码器无反馈故障（0x0004），本次运动未启动；请检查编码器接线/反馈并手动清除故障，勿自动重试"
                )
            if s.state == 0 and not s.faults:
                sensor = self.sensors()
                if not sensor["flags"] & 4:
                    raise CalibrationRejected("FPGA 拒绝 ARM：尚未完成静止校准；连接或重新下发参数后须重新校准")
            raise CalibrationRejected(f"FPGA 拒绝 ARM：state={s.state}, faults=0x{s.faults:04x}；连接保持，检查状态后再操作")

    def calibrate(self, cancel):
        self.stop()
        if self.imu_test or getattr(self, "motion_lidar", False):
            diagnostic = self.imu_diagnostics()
            if not diagnostic["ready"] or not diagnostic["sample_valid"] or diagnostic["fault"]:
                raise CalibrationRejected(f"IMU 尚未有效采样，不能校准：fault={diagnostic['fault']}；请查看IMU诊断")
            if not diagnostic["flat_install"]:
                accel = diagnostic["accel_g"]
                detail = "" if accel is None else f"；ax={accel[0]:.3f}g，ay={accel[1]:.3f}g，az={accel[2]:.3f}g"
                raise CalibrationRejected("模块未满足水平安装条件：请将PCB板面水平固定并保持静止，直到IMU诊断 flat_install=True"+detail)
        initial = self.command(0x43, reply=0xc1)
        if len(initial) != 32 or not initial[1] & 8:
            if len(initial) != 32:
                raise RuntimeError("FPGA 静止校准回复长度异常")
            raise CalibrationRejected("FPGA 拒绝静止校准：姿态或有效状态可能已变化；请保持水平静止，并检查参数和轮速为0")
        deadline = time.monotonic()+13
        while time.monotonic() < deadline and not cancel.is_set():
            result = self.sensors()
            if result["calibration"]:
                if result["calibration"] != 1 or not result["flags"] & 4:
                    reason = {2: "校准期间有运动、倾斜或角速度超限", 3: "数据过期、编码器变化或校准超时", 4: "校准已取消"}.get(result['calibration'], "校准结果异常")
                    raise CalibrationRejected(f"静止校准失败：{reason}（结果={result['calibration']}）；请查看IMU诊断后重试")
                return result
            time.sleep(.03)
        self.stop()
        raise RuntimeError("静止校准取消或超时")

    def lidar(self, duty):
        if not getattr(self, "motion_lidar", False):
            raise ValueError("需要运动+LD06固件")
        if type(duty) is not int or not (duty == 0 or 200 <= duty <= 600):
            raise ValueError("雷达PWM必须为0或200～600‰")
        self.command(0x46, struct.pack("<H", duty))
        p = self.command(0x44, struct.pack("<I", 21), reply=0xc4)
        if len(p) != 12 or struct.unpack_from("<I", p)[0] != 21:
            raise ValueError("雷达控制状态回复错误")
        word = struct.unpack_from("<I", p, 4)[0]
        return {"requested_permille": word & 1023, "effective_permille": (word >> 10) & 1023,
                "acquiring": bool(word & (1 << 20)), "expired": bool(word & (1 << 21))}

    def settle(self, cancel=None):
        self.wheels(0, 0)
        deadline = time.monotonic()+2
        quiet = None
        while time.monotonic() < deadline:
            if cancel is not None and cancel.is_set():
                return self.stop()
            self.heartbeat()
            s = self.status()
            if s.faults:
                raise CalibrationRejected(f"停车故障 0x{s.faults:04x}；FPGA已停车，连接保持")
            if abs(s.left_speed) < 20 and abs(s.right_speed) < 20:
                quiet = time.monotonic() if quiet is None else quiet
                if time.monotonic()-quiet >= .2:
                    return self.disarm()
            else:
                quiet = None
            time.sleep(.02)
        raise RuntimeError("停车稳定检查超时")

    def drive(self, calibration, linear, angular, held, cancel):
        if not held.is_set() or cancel.is_set():
            return None
        wheels = calibration.arc(linear, angular)
        if angular and not getattr(self,"imu_motion",False):
            raise ValueError("需要 IMU 运动增强固件（能力位0x400）")
        origin = self.sensors()["yaw"] if angular else 0
        self.arm(calibration)
        if not held.is_set() or cancel.is_set():
            return self.stop()
        started = time.monotonic()
        if not angular:
            self.wheels(*wheels, hold=True)
        while held.is_set() and not cancel.is_set():
            if angular:
                # arc() scales both wheel speeds together; integrate the same
                # scaled angular velocity so heading and geometry agree.
                half = math.radians(angular)*calibration.data["mechanical_track_um"]/2000
                scale = max(1, max(abs(linear-half),abs(linear+half))/calibration.data["max_speed_mm_s"])
                reference = round(origin + calibration.data["imu_yaw_sign"]*angular/scale*(time.monotonic()-started)*65536/360)
                reference = (reference+32768)%65536-32768
                self.command(0x47,struct.pack("<iih",*wheels,reference),reply=None)
            self.heartbeat()
            s = self.status()
            if s.faults or s.state == 0:
                raise CalibrationRejected(f"驾驶被FPGA停止：state={s.state}, faults=0x{s.faults:04x}；连接保持")
            time.sleep(.02)
        duration = time.monotonic()-started
        reason = "released"
        if cancel.is_set():
            reason = "cancelled"
        elif isinstance(held, HoldLease) and held.event.is_set():
            reason = "ui_lease_expired"
        status = self.stop() if cancel.is_set() else self.settle(cancel)
        return {"drive_seconds": round(duration, 3), "stop_reason": reason,
                "final_status": status}

    def rotate(self, calibration, degrees, speed, cancel):
        if cancel.is_set():
            raise RuntimeError("旋转已取消")
        if not math.isfinite(degrees) or not 1 <= abs(degrees) <= 360 or not 40 <= speed <= calibration.data["max_speed_mm_s"]:
            raise ValueError("旋转角度须为 ±1~360°，轮速须在已配置范围内")
        self.arm(calibration)
        if cancel.is_set():
            self.stop()
            raise RuntimeError("旋转已取消")
        result = self.command(0x42, struct.pack("<iH", round(degrees*65536/360), speed))
        if decode_status(result).state != 4:
            raise RuntimeError("FPGA 拒绝旋转")
        deadline = time.monotonic()+60
        while time.monotonic() < deadline and not cancel.is_set():
            self.heartbeat()
            sensor = self.sensors()
            if sensor["faults"]:
                raise CalibrationRejected(f"旋转被FPGA停止：faults=0x{sensor['faults']:04x}；连接保持")
            if not sensor["flags"] & 2:
                angle = sensor["relative"]*360/65536
                self.disarm()
                if abs(angle-degrees) > 5:
                    raise RuntimeError(f"IMU 旋转超差：{angle:.2f}°")
                return {"imu_degrees": angle, "external_degrees": None}
            time.sleep(.02)
        self.stop()
        raise RuntimeError("旋转取消或超时")

    def distance(self, calibration, mm, speed, cancel):
        if cancel.is_set():
            raise RuntimeError("距离任务已取消")
        if not math.isfinite(mm) or not 20 <= abs(mm) <= 10000 or not 40 <= speed <= calibration.data["max_speed_mm_s"]:
            raise ValueError(f"距离须为 ±20~10000 mm，速度须为40～{calibration.data['max_speed_mm_s']} mm/s")
        self.arm(calibration)
        first = self.status()
        initial = self.sensors()
        if initial["valid"] & 3 != 3 or not initial["flags"] & 4 or initial["faults"]:
            self.stop()
            raise CalibrationRejected("直线任务要求有效且已校准的IMU")
        heading = HeadingPD(calibration, initial)
        deadline = time.monotonic()+abs(mm)/40+10
        sign = 1 if mm > 0 else -1
        while time.monotonic() < deadline and not cancel.is_set():
            self.heartbeat()
            s = self.status()
            if s.faults:
                raise CalibrationRejected(f"距离任务被FPGA停止：faults=0x{s.faults:04x}；连接保持")
            distances = calibration.distance_mm(s.left_count-first.left_count, s.right_count-first.right_count)
            remaining = abs(mm)-sign*sum(distances)/2
            # Deceleration uses the same 100 Hz speed ramp as the FPGA.
            accel = calibration.data["speed_step_mm_s_per_10ms"] * 100
            stop_margin = max(5, speed*.04)
            if remaining <= stop_margin:
                last = self.settle(cancel)
                actual = calibration.distance_mm(last.left_count-first.left_count, last.right_count-first.right_count)
                error = sum(actual)/2-mm
                if abs(error) > 20:
                    raise RuntimeError(f"编码器行程超差 {error:.1f} mm；不会自动补进")
                return {"encoder_mm": actual, "encoder_error_mm": error, "external_mm": None}
            value = sign*round(max(40, min(speed, math.sqrt(2*accel*max(0, remaining-stop_margin)))))
            sensor = self.sensors()
            if sensor["valid"] & 3 != 3 or not sensor["flags"] & 4 or sensor["faults"]:
                self.stop()
                raise CalibrationRejected("直线任务IMU失效或FPGA故障；已停止")
            try:
                left, right = heading.wheels(value, sensor, calibration.data["max_speed_mm_s"])
            except ValueError as exc:
                self.stop()
                raise CalibrationRejected(str(exc)) from exc
            # Raw wheel command bypasses the FPGA heading P term, not wheel PI.
            self.wheels(left, right, hold=False)
            time.sleep(.02)
        self.stop()
        raise RuntimeError("距离任务取消或超时")

    def return_route(self, calibration, route, speed, cancel):
        if len(route)<2:
            raise ValueError("返程轨迹至少需要两个点")
        if not 40 <= speed <= calibration.data["max_speed_mm_s"]:
            raise ValueError("返程速度超出配置范围")
        current_heading=float(route[0][2])
        completed=0
        for point in route[1:]:
            if cancel.is_set():
                self.stop();raise RuntimeError("返程已取消")
            dx=float(point[0])-float(route[completed][0])
            dy=float(point[1])-float(route[completed][1])
            distance=math.hypot(dx,dy)
            if distance<30:
                completed+=1;continue
            desired=math.degrees(math.atan2(dy,dx))
            delta=(desired-current_heading+180)%360-180
            sensor=self.sensors()
            if sensor["faults"] or not sensor["flags"] & 4 or sensor["valid"] & 3 != 3:
                self.stop();raise CalibrationRejected("返程前IMU或FPGA状态无效，已停车")
            if abs(delta)>3:
                self.rotate(calibration,delta,speed,cancel)
            self.distance(calibration,distance,speed,cancel)
            current_heading=desired;completed+=1
        return {"return_route":"completed","segments":completed}

    def close(self):
        self.socket.close()
