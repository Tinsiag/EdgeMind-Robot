import math
from pathlib import Path
import random
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo import Demo
from protocol import Parser, Point, crc8
from scan import Scan, xy


# Independent table implementation from the protocol's polynomial, used only
# to construct test packets rather than calling the production encoder.
def reference_crc(data):
    table = []
    for i in range(256):
        bits = i
        for _ in range(8):
            bits = ((bits << 1) ^ (0x4D if bits & 128 else 0)) & 255
        table.append(bits)
    value = 0
    for byte in data:
        value = table[value ^ byte]
    return value


def frame(start=1000, end=1880, distance=1250, confidence=200):
    data = bytearray(struct.pack("<BBHH", 0x54, 0x2C, 3600, start))
    data.extend(struct.pack("<HB", distance, confidence) * 12)
    data.extend(struct.pack("<HH", end, 29999))
    data.append(reference_crc(data))
    return bytes(data)


class ProtocolTests(unittest.TestCase):
    def test_crc_matches_official_table_first_entries(self):
        self.assertEqual([crc8(bytes([i])) for i in range(8)],
                         [0x00, 0x4D, 0x9A, 0xD7, 0x79, 0x34, 0xE3, 0xAE])

    def test_little_endian_and_units(self):
        packet, = Parser().feed(frame())
        self.assertEqual(packet.speed_dps, 3600)
        self.assertEqual(packet.timestamp_ms, 29999)
        self.assertEqual(len(packet.points), 12)
        self.assertAlmostEqual(packet.points[0].angle_deg, 10)
        self.assertAlmostEqual(packet.points[-1].angle_deg, 18.8)
        self.assertEqual(packet.points[0].distance_mm, 1250)
        self.assertEqual(packet.points[0].confidence, 200)

    def test_every_possible_split_including_header(self):
        data = frame()
        for split in range(1, len(data)):
            parser = Parser()
            self.assertEqual(parser.feed(data[:split]), [])
            self.assertEqual(len(parser.feed(data[split:])), 1)

    def test_noise_multiframe_random_chunks(self):
        rng = random.Random(6)
        stream = b"\x00\xff\x54" + frame() * 80 + b"\x54"
        parser = Parser()
        packets = []
        while stream:
            n = rng.randrange(1, 151)
            packets.extend(parser.feed(stream[:n]))
            stream = stream[n:]
        self.assertEqual(len(packets), 80)
        self.assertEqual(parser.buffer, b"\x54")
        self.assertEqual(parser.discarded_bytes, 3)

    def test_crc_corruption_dropped_byte_and_nested_header_recover(self):
        bad = bytearray(frame())
        bad[20] ^= 0x80
        parser = Parser()
        packets = parser.feed(bytes(bad) + frame()[:15] + frame() + frame())
        self.assertEqual(len(packets), 2)
        self.assertGreaterEqual(parser.crc_errors, 2)

    def test_wrap_interpolation(self):
        packet, = Parser().feed(frame(start=35900, end=100))
        angles = [p.angle_deg for p in packet.points]
        self.assertAlmostEqual(angles[0], 359)
        self.assertAlmostEqual(angles[-1], 1)
        self.assertTrue(all(0 <= a < 360 for a in angles))
        self.assertAlmostEqual(sum((b-a) % 360 for a, b in zip(angles, angles[1:])), 2)

    def test_invalid_angle_is_rejected(self):
        parser = Parser()
        self.assertEqual(len(parser.feed(frame(start=36000) + frame())), 1)
        self.assertEqual(parser.format_errors, 1)

    def test_noise_buffer_is_bounded(self):
        parser = Parser()
        parser.feed(b"\x54\x00" * 100000)
        self.assertLessEqual(len(parser.buffer), 1)

    def test_display_coordinates_and_rotation(self):
        self.assertEqual(xy(Point(0, 1000, 100)), (0, 1))
        x, y = xy(Point(90, 2000, 100))
        self.assertAlmostEqual(x, 2)
        self.assertAlmostEqual(y, 0)
        x, y = xy(Point(0, 1000, 100), rotation=90)
        self.assertAlmostEqual(x, 1)
        self.assertAlmostEqual(y, 0)

    def test_zero_returns_replace_old_points_and_expiry(self):
        scan = Scan()
        scan.add(Parser().feed(frame())[0], 10)
        self.assertEqual(len(scan.snapshot(10)), 12)
        scan.add(Parser().feed(frame(distance=0))[0], 10.1)
        self.assertEqual(scan.snapshot(10.1), ())
        scan.add(Parser().feed(frame())[0], 11)
        self.assertEqual(scan.snapshot(12), ())

    def test_demo_roundtrip_bounded_scan(self):
        source, parser, scan = Demo(), Parser(), Scan()
        for i in range(800):
            packet, = parser.feed(source.frame())
            scan.add(packet, i / 375)
        points = scan.snapshot(800 / 375)
        self.assertGreater(len(points), 300)
        self.assertLessEqual(len(points), 720)
        self.assertTrue(all(math.isfinite(xy(p.point)[0]) for p in points))
        self.assertEqual(parser.crc_errors, 0)


if __name__ == "__main__":
    unittest.main()
