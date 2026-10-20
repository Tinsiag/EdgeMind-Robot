from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver import Receiver
from demo import Demo
from protocol import Parser


class ReceiverTests(unittest.TestCase):
    def test_open_failure_reports_error_and_closed(self):
        with patch("serial.Serial", side_effect=OSError("port busy")):
            receiver = Receiver("COM_TEST")
            receiver.start()
            receiver.join(timeout=2)
        self.assertFalse(receiver.is_alive())
        events = [receiver.events.get_nowait(), receiver.events.get_nowait()]
        self.assertEqual([e[0] for e in events], ["error", "closed"])

    def test_read_only_settings_and_clean_shutdown(self):
        receiver = Receiver("COM_TEST")

        class FakeSerial:
            in_waiting = 47
            exited = False

            def __enter__(self):
                return self

            def read(self, length):
                receiver.stop()
                return b"sample"

            def __exit__(self, *args):
                self.exited = True

        fake = FakeSerial()
        with patch("serial.Serial", return_value=fake) as opened:
            receiver.start()
            receiver.join(timeout=2)
        self.assertFalse(receiver.is_alive())
        self.assertTrue(fake.exited)
        self.assertEqual(receiver.data.get_nowait()[1], b"sample")
        self.assertEqual(receiver.received_bytes, 6)
        self.assertEqual(opened.call_args.kwargs["baudrate"], 230400)
        self.assertFalse(opened.call_args.kwargs["rtscts"])
        self.assertLessEqual(opened.call_args.kwargs["timeout"], 0.05)

    def test_batched_stream_does_not_queue_every_byte(self):
        receiver = Receiver("COM_TEST")
        source = Demo()
        stream = b"".join(source.frame() for _ in range(800))

        class FakeSerial:
            position = 0
            read_sizes = []

            # The USB driver may expose just one byte at a time. Batched reads
            # must request more bytes and let the timeout gather them.
            in_waiting = 1

            def __enter__(self):
                return self

            def read(self, length):
                self.read_sizes.append(length)
                data = stream[self.position:self.position+length]
                self.position += len(data)
                if self.position == len(stream):
                    receiver.stop()
                return data

            def __exit__(self, *args):
                pass

        fake = FakeSerial()
        with patch("serial.Serial", return_value=fake):
            receiver.start()
            receiver.join(timeout=2)
        self.assertFalse(receiver.is_alive())
        self.assertTrue(all(size == 1024 for size in fake.read_sizes))
        self.assertEqual(receiver.dropped_chunks, 0)
        self.assertLess(receiver.data.qsize(), 40)
        parser = Parser()
        while not receiver.data.empty():
            parser.feed(receiver.data.get_nowait()[1])
        self.assertEqual(parser.frames, 800)
        self.assertEqual(parser.crc_errors, 0)


if __name__ == "__main__":
    unittest.main()
