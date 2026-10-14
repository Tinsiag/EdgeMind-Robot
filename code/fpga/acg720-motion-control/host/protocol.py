"""Host-side protocol for the ACG720 motion controller."""
from __future__ import annotations

import struct
from dataclasses import dataclass

SYNC = b"\xAA\x55"
VERSION = 1
MAX_PAYLOAD = 32

HELLO = 0x01
ARM = 0x02
DISARM = 0x03
STOP = 0x04
HEARTBEAT = 0x05
SET_TWIST = 0x10
SET_WHEEL_SPEED = 0x11
ROTATE = 0x12
GET_STATUS = 0x20
CLEAR_FAULT = 0x21
SET_PARAM = 0x30


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(msg_type: int, payload: bytes = b"", seq: int = 0, ttl_ms: int = 250) -> bytes:
    if not 0 <= len(payload) <= MAX_PAYLOAD:
        raise ValueError("payload too long")
    body = struct.pack("<BBBBH", VERSION, msg_type, len(payload), seq & 0xFF, ttl_ms & 0xFFFF) + payload
    return SYNC + body + struct.pack("<H", crc16_ccitt(body))


@dataclass
class Status:
    state: int
    faults: int
    left_count: int
    right_count: int
    left_speed: int
    right_speed: int
    left_pwm: int
    right_pwm: int
    command_age_ms: int


def decode_status(payload: bytes) -> Status:
    if len(payload) < 25:
        raise ValueError(f"status payload too short: {len(payload)}")
    state = payload[0]
    faults = struct.unpack_from("<H", payload, 1)[0]
    left_count, right_count, left_speed, right_speed = struct.unpack_from("<iiii", payload, 3)
    left_pwm, right_pwm, age = struct.unpack_from("<HHH", payload, 19)
    return Status(state, faults, left_count, right_count, left_speed, right_speed, left_pwm, right_pwm, age)


class FrameParser:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, int, bytes]]:
        self.buffer.extend(data)
        result = []
        while True:
            start = self.buffer.find(SYNC)
            if start < 0:
                # Preserve a partial sync header across serial read boundaries.
                trailing_aa = self.buffer[-1:] == SYNC[:1]
                self.buffer.clear()
                if trailing_aa:
                    self.buffer.extend(SYNC[:1])
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 10:
                break
            length = self.buffer[4]
            if length > MAX_PAYLOAD:
                del self.buffer[:2]
                continue
            total = 2 + 6 + length + 2
            if len(self.buffer) < total:
                break
            body = bytes(self.buffer[2:8 + length])
            received = struct.unpack_from("<H", self.buffer, 8 + length)[0]
            del self.buffer[:total]
            if crc16_ccitt(body) != received:
                continue
            version, msg_type, _, seq, _ttl = struct.unpack_from("<BBBBH", body)
            result.append((msg_type, seq, body[6:]))
        return result


def command_payload(name: str, *args: int) -> tuple[int, bytes]:
    if name == "hello":
        return HELLO, b""
    if name == "arm":
        return ARM, b""
    if name == "disarm":
        return DISARM, b""
    if name == "stop":
        return STOP, b""
    if name == "status":
        return GET_STATUS, b""
    if name == "clear-fault":
        return CLEAR_FAULT, b""
    if name == "forward":
        return SET_TWIST, struct.pack("<ii", int(args[0]), 0)
    if name == "backward":
        return SET_TWIST, struct.pack("<ii", -abs(int(args[0])), 0)
    if name == "turn":
        return SET_TWIST, struct.pack("<ii", int(args[0]), int(args[1]))
    if name == "rotate":
        return ROTATE, struct.pack("<iH", int(args[0] * 1000), int(args[1]))
    if name == "set-param":
        return SET_PARAM, struct.pack("<BI", int(args[0]), int(args[1]))
    raise ValueError(f"unknown command: {name}")
