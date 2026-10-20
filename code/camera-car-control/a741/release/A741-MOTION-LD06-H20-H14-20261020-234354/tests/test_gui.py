import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch, Mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
spec = importlib.util.spec_from_file_location("a741_app", ROOT / "host/app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


class GuiTests(unittest.TestCase):
    def test_calibration_rejection_keeps_connection(self):
        import queue
        app = object.__new__(app_module.App)
        app.shutdown = threading.Event();app.cancel = threading.Event()
        app.jobs = queue.Queue();app.events = queue.Queue()
        app.client = Mock();app.cleanup = Mock()
        app.client.calibrate.side_effect = app_module.CalibrationRejected("请保持水平静止")
        app.jobs.put(("calibrate", ()))
        worker = threading.Thread(target=app.worker, daemon=True)
        worker.start()
        try:
            self.assertEqual(app.events.get(timeout=2), ("error", "请保持水平静止"))
            self.assertEqual(app.events.get(timeout=2), ("idle", None))
            app.cleanup.assert_not_called()
        finally:
            app.shutdown.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

    def test_layout_frame_and_clean_shutdown_without_network(self):
        root = tk.Tk()
        app = app_module.App(root)
        try:
            for size in ("1280x850", "1000x720"):
                root.geometry(size)
                root.update()
                app.frames.put((Image.new("RGB", (400, 240), "#267f5c"), 123, time.monotonic()))
                app.refresh()
                root.update()
                self.assertIsNotNone(app.photo)
                self.assertGreater(app.camera.winfo_width(), 300)
                self.assertGreater(app.radar.winfo_width(), 150)
                self.assertLessEqual(app.log_view.winfo_y()+app.log_view.winfo_height(), root.winfo_height())
                self.assertFalse(app.connected)
                self.assertIsNone(app.client)
                self.assertEqual(str(app.lidar_start.cget("state")),"disabled")
                app.sensor_tabs.select(1);root.update()
                app.draw_map(bytes([127])*(600*600),(15000,15000,0),((15000,15000,0),(15100,15000,0)),1)
                self.assertIsNotNone(app.map_photo)
                before=app.map_zoom;app.zoom_map(1.25)
                self.assertGreater(app.map_zoom,before)
                center=app.map_center;app.map_drag=(20,20)
                event=Mock(x=40,y=30);app.pan_map(event)
                self.assertNotEqual(app.map_center,center)
                self.assertTrue(any(app.map_canvas.type(item)=="image" for item in app.map_canvas.find_all()))
            app.screenshot()
            self.assertTrue(list(app.session_dir.glob("frame-123-*.json")))
        finally:
            app.shutdown.set();app.cancel.set();app.thread.join(timeout=2)
            app.mapper.close();app.logfile.close();root.destroy()
        self.assertFalse(app.thread.is_alive())

    def test_stop_cancels_busy_motion_and_clears_lidar_request(self):
        app=object.__new__(app_module.App)
        app.lidar_requested=True;app.held=app_module.HoldLease();app.held.set()
        app.cancel=threading.Event();app.busy=True;app.connected=True;app.submit=Mock()
        app.stop()
        self.assertFalse(app.lidar_requested);self.assertFalse(app.held.is_set())
        self.assertTrue(app.cancel.is_set());app.submit.assert_not_called()

    def test_deadman_ui_stall(self):
        from client import HoldLease
        lease = HoldLease()
        with patch("client.time.monotonic", return_value=10):
            lease.set()
        with patch("client.time.monotonic", return_value=10.1):
            self.assertTrue(lease.is_set())
            lease.renew()
        with patch("client.time.monotonic", return_value=10.31):
            self.assertFalse(lease.is_set())
            lease.renew()
            self.assertFalse(lease.is_set())
