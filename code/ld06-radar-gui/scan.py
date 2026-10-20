"""Bounded rolling polar scan; independent of Tk and serial I/O."""
from dataclasses import dataclass
import math
from protocol import Packet, Point


@dataclass(frozen=True)
class Sample:
    point: Point
    received_at: float


class Scan:
    def __init__(self):
        self.bins: dict[int, Sample] = {}
        self.latest_angle = 0.0
        self.speed_dps = 0
        self.last_packet_at = None

    def clear(self):
        self.bins.clear()
        self.last_packet_at = None
        self.speed_dps = 0

    def add(self, packet: Packet, now: float):
        # Clear the entire newly scanned arc, including invalid returns, to avoid
        # retaining an old obstacle when the new measurement is zero.
        span = (packet.end_deg - packet.start_deg) % 360
        for key, sample in list(self.bins.items()):
            if (sample.point.angle_deg - packet.start_deg) % 360 <= span + 1e-7:
                del self.bins[key]
        for point in packet.points:
            key = int(point.angle_deg * 2) % 720
            if point.distance_mm > 0:
                self.bins[key] = Sample(point, now)
            else:
                self.bins.pop(key, None)
        self.latest_angle = packet.end_deg
        self.speed_dps = packet.speed_dps
        self.last_packet_at = now

    def snapshot(self, now: float, retention: float = 0.6) -> tuple[Sample, ...]:
        for key in list(self.bins):
            if now - self.bins[key].received_at > retention:
                del self.bins[key]
        return tuple(self.bins.values())


def xy(point: Point, rotation: float = 0) -> tuple[float, float]:
    """Display coordinates in meters: +x right, +y up, clockwise from up."""
    angle = math.radians(point.angle_deg + rotation)
    distance = point.distance_mm / 1000
    return distance * math.sin(angle), distance * math.cos(angle)
