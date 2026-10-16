"""Host parser regression; no serial device or motor commands required."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from protocol import FrameParser, frame

class ParserTests(unittest.TestCase):
    def setUp(self):
        self.payload = bytes(range(25))
        self.packet = frame(0x80, self.payload, seq=7, ttl_ms=0)
        self.expected = [(0x80, 7, self.payload)]

    def test_every_split(self):
        for split in range(len(self.packet)+1):
            with self.subTest(split=split):
                parser = FrameParser()
                self.assertEqual(parser.feed(self.packet[:split])+parser.feed(self.packet[split:]), self.expected)

    def test_bytewise(self):
        parser = FrameParser()
        results = []
        for byte in self.packet:
            results += parser.feed(bytes([byte]))
        self.assertEqual(results, self.expected)

    def test_noise_then_partial_sync(self):
        parser = FrameParser()
        self.assertEqual(parser.feed(b'noise\xaa'), [])
        self.assertEqual(parser.feed(self.packet[1:]), self.expected)

    def test_crc_rejected_then_recovery(self):
        bad = bytearray(self.packet)
        bad[-1] ^= 1
        parser = FrameParser()
        self.assertEqual(parser.feed(bytes(bad)+self.packet), self.expected)

    def test_two_frames(self):
        self.assertEqual(FrameParser().feed(self.packet*2), self.expected*2)

if __name__ == '__main__':
    unittest.main()
