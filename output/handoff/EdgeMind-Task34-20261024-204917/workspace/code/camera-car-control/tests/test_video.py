from pathlib import Path
import queue
import socket
import struct
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from video import FrameAssembler, VideoReceiver, packet, rgb565_image, COMMIT, ABORT


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.parser = FrameAssembler()
        self.pixels = bytes.fromhex('f800 07e0 001f ffff')

    def test_requires_complete_frame_and_commit(self):
        self.assertIsNone(self.parser.feed(packet(1, 2, 2, 0, pixels=self.pixels[:4]), 0))
        self.assertIsNone(self.parser.feed(packet(1, 2, 2, flags=COMMIT), 0.1))
        result = self.parser.feed(packet(1, 2, 2, 1, pixels=self.pixels[4:]), 0.2)
        self.assertEqual(result, (1, 2, 2, self.pixels))

    def test_out_of_order_commit_first_and_duplicate(self):
        self.parser.feed(packet(3, 2, 2, flags=COMMIT), 0)
        row = packet(3, 2, 2, 1, pixels=self.pixels[4:])
        self.parser.feed(row, 0.1)
        self.parser.feed(row, 0.2)
        self.assertEqual(self.parser.feed(packet(3, 2, 2, pixels=self.pixels[:4]), 0.3)[3], self.pixels)

    def test_conflicting_overlap_poisoned(self):
        self.parser.feed(packet(1, 2, 2, pixels=self.pixels[:4]), 0)
        self.parser.feed(packet(1, 2, 2, pixels=b'\0'*4), 0.1)
        self.assertIsNone(self.parser.feed(packet(1, 2, 2, flags=COMMIT), 0.2))
        self.assertNotIn(1, self.parser.pending)
        self.assertEqual(self.parser.invalid, 1)

    def test_bad_frame_never_published(self):
        self.parser.feed(packet(1, 2, 2, pixels=self.pixels[:4]), 0)
        self.parser.feed(packet(1, 2, 2, flags=ABORT), 0.1)
        self.parser.feed(packet(1, 2, 2, 1, pixels=self.pixels[4:]), 0.2)
        self.assertIsNone(self.parser.feed(packet(1, 2, 2, flags=COMMIT), 0.3))
        self.assertEqual(self.parser.completed, 0)

    def test_timeout_and_memory_limit(self):
        self.parser.feed(packet(1, 2, 2, flags=COMMIT), 0)
        self.parser.feed(packet(2, 2, 2, flags=COMMIT), 0.1)
        self.parser.feed(packet(3, 2, 2, flags=COMMIT), 0.2)
        self.assertEqual(len(self.parser.pending), 2)
        self.parser.expire(1)
        self.assertEqual(self.parser.pending, {})
        self.assertEqual(self.parser.dropped, 3)

    def test_rejects_bad_lengths_dimensions_and_coordinates(self):
        malformed = [b'', b'EMV1', packet(1, 2, 2, pixels=self.pixels[:4])[:-1],
                     packet(1, 0, 2, flags=COMMIT), packet(1, 2000, 2, flags=COMMIT),
                     packet(1, 2, 2, 2, pixels=self.pixels[:4]),
                     packet(1, 2, 2, 0, 1, self.pixels[:4]),
                     packet(1, 2, 2, pixels=self.pixels[:4], flags=COMMIT),
                     packet(1, 2, 2, flags=99)]
        for data in malformed:
            self.assertIsNone(self.parser.feed(data, 0))
        self.assertEqual(self.parser.invalid, len(malformed))

    def test_resolution_cannot_change_inside_frame(self):
        self.parser.feed(packet(1, 2, 2, flags=COMMIT), 0)
        self.assertIsNone(self.parser.feed(packet(1, 3, 2, pixels=self.pixels[:4]), 0.1))
        self.assertNotIn(1, self.parser.pending)

    def complete(self, fid, now):
        self.parser.feed(packet(fid, 2, 2, pixels=self.pixels[:4]), now)
        self.parser.feed(packet(fid, 2, 2, 1, pixels=self.pixels[4:]), now)
        return self.parser.feed(packet(fid, 2, 2, flags=COMMIT), now)

    def test_frame_id_wrap_and_old_frame_rejection(self):
        self.assertIsNotNone(self.complete(0xFFFFFFFF, 0))
        self.assertIsNotNone(self.complete(0, 0.1))
        self.assertIsNone(self.complete(0xFFFFFFFE, 0.2))

    def test_sender_restart_after_silence(self):
        self.complete(100, 0)
        self.assertIsNone(self.complete(0, 0.1))
        self.assertIsNotNone(self.complete(0, 3))

    def test_rgb565_channel_order(self):
        image = rgb565_image(2, 2, self.pixels)
        self.assertEqual([image.getpixel((x, y)) for y in range(2) for x in range(2)],
                         [(255,0,0),(0,255,0),(0,0,255),(255,255,255)])

    def test_loopback_udp_receives_only_allowed_source(self):
        frames, events = queue.Queue(maxsize=1), queue.Queue()
        worker = VideoReceiver('127.0.0.1', 0, '127.0.0.1', frames, events)
        worker.start()
        try:
            self.assertTrue(worker.bound.wait(2))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                for row in range(2):
                    sock.sendto(packet(8, 2, 2, row, pixels=self.pixels[row*4:row*4+4]), worker.address)
                sock.sendto(packet(8, 2, 2, flags=COMMIT), worker.address)
            image, fid, _ = frames.get(timeout=2)
            self.assertEqual(fid, 8)
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        finally:
            worker.stop()
            worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_latest_queue_is_bounded(self):
        from video import latest_put
        frames = queue.Queue(maxsize=1)
        for number in range(100):
            latest_put(frames, number)
        self.assertEqual(frames.qsize(), 1)
        self.assertEqual(frames.get(), 99)


if __name__ == '__main__':
    unittest.main()
