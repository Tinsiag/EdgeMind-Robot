"""Synthetic room, explicitly a demo. Encoded as real LD06-format packets."""
import math
import random
import struct
from protocol import crc8


class Demo:
    def __init__(self):
        self.index = 0
        self.random = random.Random(6)

    def frame(self) -> bytes:
        start = (self.index * 960) % 36000
        frame = bytearray(struct.pack("<BBHH", 0x54, 0x2C, 3600, start))
        for i in range(12):
            angle = math.radians((start + 80 * i) / 100)
            dx, dy = math.sin(angle), math.cos(angle)
            distances = [3.4 / abs(dx) if abs(dx) > 1e-9 else 1e9,
                         (2.6 if dy >= 0 else 2.0) / abs(dy) if abs(dy) > 1e-9 else 1e9]
            # A round obstacle, 0.4 m in radius, at (-1.2, 1.1) m.
            projection = dx * -1.2 + dy * 1.1
            discriminant = projection**2 - (1.2**2 + 1.1**2 - 0.4**2)
            if discriminant >= 0 and projection > 0:
                distances.append(projection - math.sqrt(discriminant))
            distance = max(1, round(min(distances) * 1000 + self.random.gauss(0, 8)))
            frame.extend(struct.pack("<HB", distance, 180 + self.random.randrange(60)))
        frame.extend(struct.pack("<HH", (start + 880) % 36000,
                                 round(self.index * 1000 / 375) % 30000))
        frame.append(crc8(frame))
        self.index += 1
        return bytes(frame)
