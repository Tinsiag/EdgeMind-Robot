"""Single-owner UDP control client. Motion commands are never retried."""
from pathlib import Path
import socket
import struct
import sys
import time
import ipaddress
from dataclasses import dataclass

MOTION_HOST = Path(__file__).resolve().parents[2].parent / "fpga" / "acg720-motion-control" / "host"
sys.path.insert(0, str(MOTION_HOST))
from protocol import FrameParser, crc16_ccitt, decode_status, frame


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
        if getattr(self,"sensors_only",False) and (kind in (2,0x11,0x42,0x45,0x47) or (kind==0x59 and payload[:1]==b"\x01")):
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
            # Bound host traffic to the FPGA's single command slot.
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

    def wheels(self, left, right):
        self.command(0x11, struct.pack("<ii", left, right), reply=None)

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





    def close(self):
        self.socket.close()
