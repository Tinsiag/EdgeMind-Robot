"""Real Tk smoke checks; requires a graphical session, no LiDAR required."""
import csv
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import RadarApp
from demo import Demo


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = RadarApp(self.root)

    def tearDown(self):
        self.app.close()

    def refresh(self):
        self.root.after_cancel(self.app.timer)
        self.app.tick()

    def test_demo_pause_export_and_expiry(self):
        app = self.app
        app.toggle_demo()
        source = Demo()
        now = time.monotonic()
        for _ in range(40):
            app.feed(source.frame(), now)
        self.refresh()
        self.assertGreater(len(app.visible), 300)
        app.toggle_pause()
        self.refresh()
        frozen = app.visible
        app.scan.clear()
        self.refresh()
        self.assertEqual(app.visible, frozen)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cloud.csv"
            app.save_csv(target)
            with target.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), len(frozen))
            self.assertEqual(rows[0]["source"], "demo")
        app.toggle_demo()
        self.refresh()
        self.assertEqual(app.visible, ())
        self.assertEqual(app.stats["hz"].get(), "— Hz")

    def test_filter_and_live_expiry(self):
        app = self.app
        source = Demo()
        for _ in range(40):
            app.feed(source.frame(), time.monotonic())
        self.refresh()
        self.assertGreater(len(app.visible), 300)
        app.radius.set("1")
        self.refresh()
        self.assertEqual(app.visible, ())
        app.radius.set("6")
        for key, sample in list(app.scan.bins.items()):
            app.scan.bins[key] = type(sample)(sample.point, time.monotonic() - 3)
        self.refresh()
        self.assertEqual(app.visible, ())

    def test_auto_range_close_echo_and_wheel_zoom(self):
        from protocol import Packet, Point
        from types import SimpleNamespace
        app = self.app
        packet = Packet(3600, 0, 0, 8.8,
                        tuple(Point(i*0.8, 250, 200) for i in range(12)))
        app.scan.add(packet, time.monotonic())
        self.refresh()
        self.assertEqual(app.radius.get(), "自动")
        self.assertEqual(app.display_radius, 0.3)
        self.assertEqual(app.stats["near"].get(), "25 cm")
        self.assertTrue(app.canvas.find_all())
        app.zoom(SimpleNamespace(delta=120))
        self.assertEqual(app.radius.get(), "0.2")

    def test_raw_chunk_loss_discards_partial_packet_before_resuming(self):
        from receiver import Receiver
        app = self.app
        source = Demo()
        frame = source.frame()
        app.feed(frame[:15], time.monotonic())
        receiver = Receiver("COM_TEST")
        receiver.dropped_chunks = 1
        receiver.data.put((time.monotonic(), source.frame()))
        app.worker = receiver
        app._read_worker()
        self.assertEqual(app.parser.frames, 1)
        self.assertEqual(app.parser.crc_errors, 0)
        app.worker = None


if __name__ == "__main__":
    unittest.main()
