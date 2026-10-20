"""LD06 streaming protocol: 230400 8N1, 47 bytes, little endian, CRC8/0x4D."""
from dataclasses import dataclass
import struct

HEADER = b"\x54\x2c"
FRAME_SIZE = 47
POINT_COUNT = 12


def crc8(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value << 1) ^ (0x4D if value & 0x80 else 0)) & 0xFF
    return value


@dataclass(frozen=True)
class Point:
    angle_deg: float
    distance_mm: int
    confidence: int


@dataclass(frozen=True)
class Packet:
    speed_dps: int
    timestamp_ms: int
    start_deg: float
    end_deg: float
    points: tuple[Point, ...]


class Parser:
    """Keep partial frames; on errors advance ONE byte so a nested header survives."""

    def __init__(self):
        self.buffer = bytearray()
        self.frames = 0
        self.crc_errors = 0
        self.format_errors = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> list[Packet]:
        self.buffer.extend(data)
        packets = []
        while True:
            pos = self.buffer.find(HEADER)
            if pos < 0:
                keep = int(self.buffer.endswith(HEADER[:1]))
                discard = len(self.buffer) - keep
                self.discarded_bytes += discard
                del self.buffer[:discard]
                break
            if pos:
                self.discarded_bytes += pos
                del self.buffer[:pos]
            if len(self.buffer) < FRAME_SIZE:
                break
            frame = bytes(self.buffer[:FRAME_SIZE])
            if crc8(frame[:-1]) != frame[-1]:
                self.crc_errors += 1
                self.discarded_bytes += 1
                del self.buffer[0]
                continue
            speed, start = struct.unpack_from("<HH", frame, 2)
            end, stamp = struct.unpack_from("<HH", frame, 42)
            if start >= 36000 or end >= 36000:
                self.format_errors += 1
                self.discarded_bytes += FRAME_SIZE
                del self.buffer[:FRAME_SIZE]
                continue
            span = (end - start) % 36000
            points = tuple(
                Point(((start + span * i / 11) / 100) % 360,
                      *struct.unpack_from("<HB", frame, 6 + i * 3))
                for i in range(POINT_COUNT)
            )
            packets.append(Packet(speed, stamp, start / 100, end / 100, points))
            self.frames += 1
            del self.buffer[:FRAME_SIZE]
        return packets
