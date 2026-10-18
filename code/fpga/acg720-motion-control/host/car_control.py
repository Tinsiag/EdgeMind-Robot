"""Encoder-based relative moves for A720/A721/A722. No hardware opens on import."""
from dataclasses import dataclass
import math
import struct
import threading
import time

from protocol import ARM, GET_STATUS, SET_PARAM, SET_WHEEL_SPEED, STOP, decode_status, frame
from serial_control import send_and_read


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
            arc = math.pi * 121.4 * self.amount / 360
            lengths = (-arc, arc) if self.action == 'left' else (arc, -arc)
        targets = tuple(round(mm * cpr / (math.pi * 66.3))
                        for mm, cpr in zip(lengths, (1469, 1471)))
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
        cancel = cancel if cancel is not None else threading.Event()
        failure = None
        completed = False
        try:
            self.stop()
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
            longest_mm = max(abs(n) * math.pi * 66.3 / cpr
                             for n, cpr in zip(targets, (1469, 1471)))
            deadline = self.clock() + min(60, max(5, longest_mm / move.speed * 4 + 3))
            reached = [n == 0 for n in targets]
            while not all(reached):
                if cancel.is_set():
                    return False
                if self.clock() >= deadline:
                    raise RuntimeError('动作超时，未完成指定距离/角度')
                commands = []
                for i, (count, origin, target, cpr) in enumerate(zip(
                        (status.left_count, status.right_count), origins, targets, (1469, 1471))):
                    sign = 1 if target >= 0 else -1
                    progress = count_delta(count, origin) * sign
                    if progress < -20:
                        raise RuntimeError('编码器方向与运动目标相反，请检查驱动与反馈极性')
                    remaining = abs(target) - progress
                    if remaining <= 2:
                        reached[i] = True
                    mm_left = max(0, remaining) * math.pi * 66.3 / cpr
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
