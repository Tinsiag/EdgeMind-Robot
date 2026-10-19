"""Encoder-based relative moves for A720/A721/A722. No hardware opens on import."""
from dataclasses import dataclass
import math
import struct
import threading
import time

from protocol import (ARM, GET_STATUS, SET_PARAM, SET_WHEEL_SPEED, STOP, decode_status, frame,
                      GET_CAPABILITIES, SET_MODE, START_LINE, GET_SENSING, SET_LINE_PARAM,
                      decode_capabilities, decode_sensing)
from serial_control import send_and_read
from synchronized_motion import SynchronizedMove

# Effective chassis calibration. Measure on the floor and update these values
# together with the matching encoder configuration when the hardware changes.
WHEEL_DIAMETER_MM = 66.3
# Provisional floor correction: 260 mm produced about 100 deg for a 90 deg command.
EFFECTIVE_WHEEL_BASE_MM = 234.0
ENCODER_CPR = (1469, 1471)


@dataclass(frozen=True)
class Move:
    action: str
    amount: float  # cm for forward/backward, degrees for left/right
    speed: int = 200  # mm/s, per wheel

    def validate(self):
        if self.action not in ('forward', 'backward', 'left', 'right'):
            raise ValueError('未知动作')
        limit = 200 if self.action in ('forward', 'backward') else 360
        if not math.isfinite(self.amount) or not 0 < self.amount <= limit:
            raise ValueError(f'距离须大于0且不超过200厘米；角度须大于0且不超过360度')
        if not 40 <= self.speed <= 400:
            raise ValueError('轮速须为40～400 mm/s')

    def targets(self):
        """Signed relative encoder targets; left turn = left backward/right forward."""
        self.validate()
        if self.action in ('forward', 'backward'):
            length = self.amount * 10 * (1 if self.action == 'forward' else -1)
            lengths = (length, length)
        else:
            arc = math.pi * EFFECTIVE_WHEEL_BASE_MM * self.amount / 360
            lengths = (-arc, arc) if self.action == 'left' else (arc, -arc)
        targets = tuple(round(mm * cpr / (math.pi * WHEEL_DIAMETER_MM))
                        for mm, cpr in zip(lengths, ENCODER_CPR))
        if min(abs(n) for n in targets) <= 2:
            raise ValueError('目标太小，请至少输入0.1厘米或1度')
        return targets


def count_delta(current, start):
    """Signed modulo-32 difference for encoder counter wrap."""
    return (current - start + 2**31) % 2**32 - 2**31


class CarController:
    def __init__(self, port, notify=lambda text: None, clock=time.monotonic,
                 sleep=time.sleep, right_motor_reversed=True):
        self.port, self.notify = port, notify
        self.clock, self.sleep = clock, sleep
        self.seq = 0
        # Physical right bridge runs backward for a positive UART target.
        # Count targets remain forward-positive; only transmitted target flips.
        # Firmware PI still sees its original feedback sign (see host README).
        self.right_motor_reversed = right_motor_reversed
        self.capabilities = None
        self.synchronized_motion = False

    def detect_capabilities(self):
        """Read-only probe; an absent reply preserves legacy compensation."""
        self.seq = (self.seq + 1) & 255
        packets = send_and_read(self.port, GET_CAPABILITIES, b'', self.seq, 0.12)
        matches = [data for kind, seq, data in packets if kind == 0xC0 and seq == self.seq]
        if not matches:
            return None
        self.capabilities = decode_capabilities(matches[-1])
        if self.capabilities.bridge_fixed:
            self.right_motor_reversed = False
            self.synchronized_motion = True
        return self.capabilities

    def sensing(self):
        if self.capabilities is None or not self.capabilities.has_vision:
            raise RuntimeError('当前固件不支持视觉与测距接口')
        self.seq = (self.seq + 1) & 255
        packets = send_and_read(self.port, GET_SENSING, b'', self.seq, 0.12)
        matches = [data for kind, seq, data in packets if kind == 0xC3 and seq == self.seq]
        if not matches:
            raise RuntimeError('没有匹配的感知状态回复')
        return decode_sensing(matches[-1])

    def set_mode(self, autonomous):
        if self.capabilities is None or not self.capabilities.has_vision:
            raise RuntimeError('当前固件不支持模式切换')
        self.stop()
        self.request(SET_MODE, bytes([int(bool(autonomous))]))
        status = self.sensing()
        if status.mode != int(bool(autonomous)) or status.armed:
            raise RuntimeError('模式切换未确认')

    def start_line(self, cancel=None):
        try:
            return self._start_line(cancel)
        except BaseException:
            try:
                self.stop()
            except Exception as exc:
                self.notify(f'循线启动异常，停车通信未确认：{exc}')
            raise

    def _start_line(self, cancel=None):
        def cancelled():
            return cancel is not None and cancel.is_set()
        if cancelled():
            self.stop()
            return self.sensing()
        self.set_mode(True)
        if cancelled():
            self.stop()
            return self.sensing()
        self.param(9, 512)
        if cancelled():
            self.stop()
            return self.sensing()
        self.request(START_LINE)
        status = self.sensing()
        if not status.armed:
            raise RuntimeError('循线未启动：' + status.stop_reason + '；检查三次安全测距、黑线及视频就绪')
        return status

    def line_param(self, key, value):
        if self.capabilities is None or not self.capabilities.has_vision:
            raise RuntimeError('当前固件不支持循线参数')
        if self.sensing().armed:
            raise RuntimeError('先停止，再修改循线参数')
        limits = {0: (1, 254), 1: (0, 479), 2: (0, 479), 3: (0, 479),
                  4: (0, 479), 5: (0, 1), 6: (0, 1024), 7: (0, 1024), 8: (0, 500)}
        if key not in limits or not limits[key][0] <= value <= limits[key][1]:
            raise ValueError('循线参数超出范围')
        self.request(SET_LINE_PARAM, struct.pack('<BI', key, value))

    def request(self, kind, payload=b''):
        self.seq = (self.seq + 1) & 255
        packets = send_and_read(self.port, kind, payload, self.seq, 0.12)
        matches = [data for response_kind, seq, data in packets
                   if response_kind == 0x80 and seq == self.seq]
        if not matches:
            raise RuntimeError('串口没有匹配回复，已停止任务；请检查连接')
        return decode_status(matches[-1])

    def status(self):
        return self.request(GET_STATUS)

    def param(self, key, value):
        self.request(SET_PARAM, struct.pack('<BI', key, value))

    def stop(self):
        """Try STOP and zero cap independently; verify digital output status."""
        errors = []
        for operation in (lambda: self.request(STOP), lambda: self.param(9, 0)):
            try:
                operation()
            except Exception as exc:
                errors.append(str(exc))
        try:
            status = self.status()
            if status.state not in (0, 3) or status.left_pwm or status.right_pwm:
                errors.append('停车状态未确认')
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise RuntimeError('停车通信不完整，请断开VM：' + '；'.join(errors))

    def move(self, move, cancel=None):
        targets = move.targets()  # Validate before any configuration or ARM.
        if self.capabilities is not None and move.speed > self.capabilities.max_speed:
            raise ValueError(f'当前固件轮速最高 {self.capabilities.max_speed} mm/s')
        cancel = cancel if cancel is not None else threading.Event()
        failure = None
        completed = False
        try:
            self.stop()
            if self.capabilities is not None and self.capabilities.has_vision:
                self.set_mode(False)
            status = self.status()
            if status.faults:
                raise RuntimeError(f'FPGA故障 faults={status.faults}，请先排查；程序不会自动清故障')
            for key, value in [(9, 0), (0, 1469), (1, 1471), (2, 66), (3, 66),
                               (4, 121), (5, 400), (6, 491), (10, 50)]:
                if cancel.is_set():
                    return False
                self.param(key, value)
            if cancel.is_set():
                return False
            self.request(ARM)
            status = self.status()
            if status.state != 1 or status.faults:
                raise RuntimeError('ARM未确认或存在故障，未发送运动目标')
            origins = (status.left_count, status.right_count)
            self.param(9, 512)
            if self.synchronized_motion:
                return self._move_synchronized(move, targets, origins, status, cancel)
            longest_mm = max(abs(n) * math.pi * WHEEL_DIAMETER_MM / cpr
                             for n, cpr in zip(targets, ENCODER_CPR))
            deadline = self.clock() + min(60, max(5, longest_mm / move.speed * 4 + 3))
            reached = [n == 0 for n in targets]
            while not all(reached):
                if cancel.is_set():
                    return False
                if self.clock() >= deadline:
                    raise RuntimeError('动作超时，未完成指定距离/角度')
                commands = []
                for i, (count, origin, target, cpr) in enumerate(zip(
                        (status.left_count, status.right_count), origins, targets, ENCODER_CPR)):
                    sign = 1 if target >= 0 else -1
                    progress = count_delta(count, origin) * sign
                    if progress < -20:
                        raise RuntimeError('编码器方向与运动目标相反，请检查驱动与反馈极性')
                    remaining = abs(target) - progress
                    mm_left = max(0, remaining) * math.pi * WHEEL_DIAMETER_MM / cpr
                    if remaining <= 2:
                        reached[i] = True
                    speed = min(move.speed, max(40, round(mm_left * 4)))
                    commands.append(0 if reached[i] else sign * speed)
                if all(reached):
                    completed = True
                    break
                # Each velocity frame renews FPGA's default 250 ms TTL.
                if self.right_motor_reversed:
                    commands[1] = -commands[1]
                self.seq = (self.seq + 1) & 255
                self.port.write(frame(SET_WHEEL_SPEED, struct.pack('<ii', *commands), self.seq))
                self.sleep(0.04)
                status = self.status()
                self.notify(status)
                if status.faults or status.state in (0, 3):
                    raise RuntimeError(f'运动停止：state={status.state}，faults={status.faults}')
            return completed
        except BaseException as exc:
            failure = exc
            raise
        finally:
            try:
                self.stop()
            except Exception as exc:
                if failure is None:
                    raise
                self.notify(f'{exc}；原错误：{failure}')

    def _move_synchronized(self, move, targets, origins, status, cancel):
        planner = SynchronizedMove(targets, origins, move.speed)
        longest_mm = max(planner.lengths)
        deadline = self.clock() + min(60, max(8, longest_mm / move.speed * 6 + 6))
        self.notify('双轮同步减速：FPGA轮速PI + 主机行程反馈；等待低速稳定后结束')
        while True:
            if cancel.is_set():
                return False
            now = self.clock()
            if now >= deadline:
                raise RuntimeError('动作超时，未完成同步行程/停稳检查')
            if status.faults or status.state not in (1, 2):
                raise RuntimeError(f'运动停止：state={status.state}，faults={status.faults}')
            commands = planner.step(status, now)
            if commands is None:
                self.notify(f'遥测低速稳定；剩余轮周行程 左{planner.errors_mm[0]:.1f}/右{planner.errors_mm[1]:.1f}mm')
                return True
            self.seq = (self.seq + 1) & 255
            self.port.write(frame(SET_WHEEL_SPEED, struct.pack('<ii', *commands), self.seq))
            self.sleep(0.04)
            status = self.status()
            self.notify(status)
