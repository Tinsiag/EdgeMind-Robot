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
    def test_connect_calibrates_once_without_arming_and_preserves_rejected_connection(self):
        import queue
        from dataclasses import dataclass
        @dataclass
        class Status:
            state: int = 0
        for rejection in (False, True):
            app=object.__new__(app_module.App)
            app.shutdown=threading.Event();app.cancel=threading.Event()
            app.jobs=queue.Queue();app.events=queue.Queue();app.frames=queue.Queue()
            app.cleanup=Mock();app.calibration=Mock();app.sensors_only=False
            c=Mock(imu_test=False,motion_lidar=True)
            c.connect.return_value=Status()
            if rejection:
                c.calibrate.side_effect=app_module.CalibrationRejected("请保持水平静止")
            else:
                c.calibrate.return_value={"flags":4,"calibration":1}
            with patch.object(app_module,"Client",return_value=c),patch.object(app_module,"TelemetryReceiver"),patch.object(app_module,"VideoReceiver"):
                app.jobs.put(("connect",("192.168.0.2",)))
                thread=threading.Thread(target=app.worker,daemon=True);thread.start()
                seen=[]
                try:
                    while True:
                        event=app.events.get(timeout=2);seen.append(event)
                        if event[0]=="idle":break
                    c.calibrate.assert_called_once_with(app.cancel)
                    c.arm.assert_not_called()
                    self.assertEqual(app.cleanup.call_count,1)
                    self.assertTrue(any(k=="connected" for k,v in seen))
                    self.assertEqual(any(k=="error" for k,v in seen),rejection)
                finally:
                    app.shutdown.set();thread.join(timeout=2)

    def test_motion_speed_rejects_input_above_configured_limit_before_submit(self):
        from calibration import Calibration
        app=object.__new__(app_module.App)
        app.calibration=Calibration.load();app.speed=Mock();app.distance=Mock()
        app.speed.get.return_value=401;app.distance.get.return_value=20
        app.submit=Mock()
        with patch.object(app_module.messagebox,"showerror") as error:
            app.motion_job("distance")
            error.assert_called_once()
            self.assertIn("400",error.call_args.args[1])
        app.submit.assert_not_called()
        app.speed.get.return_value=400
        app.motion_job("distance")
        app.submit.assert_called_once_with("distance",200,400)

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

    def test_encoder_arm_rejection_keeps_control_and_telemetry_connected(self):
        import queue
        app=object.__new__(app_module.App)
        app.shutdown=threading.Event();app.cancel=threading.Event()
        app.jobs=queue.Queue();app.events=queue.Queue();app.lidar_requested=False
        app.client=Mock();app.client.drive.side_effect=app_module.CalibrationRejected("FPGA 已锁存编码器无反馈故障（0x0004）")
        app.cleanup=Mock();app.held=app_module.HoldLease();app.calibration=Mock();app.telemetry=None
        app.events.put(("connected", {"state":3,"faults":4}))
        app.jobs.put(("drive", (100,0)))
        worker=threading.Thread(target=app.worker,daemon=True);worker.start()
        try:
            seen=[]
            while True:
                event=app.events.get(timeout=2);seen.append(event)
                if event[0]=="idle":break
            self.assertIn(("error", "FPGA 已锁存编码器无反馈故障（0x0004）"),seen)
            app.cleanup.assert_not_called()
        finally:
            app.shutdown.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

    def test_clear_fault_confirms_fpga_status_before_reporting_success(self):
        import queue
        app=object.__new__(app_module.App)
        app.shutdown=threading.Event();app.cancel=threading.Event()
        app.jobs=queue.Queue();app.events=queue.Queue();app.lidar_requested=False
        app.client=Mock();app.client.status.return_value=Mock(faults=0)
        app.cleanup=Mock();app.telemetry=None
        app.jobs.put(("clear",()))
        worker=threading.Thread(target=app.worker,daemon=True);worker.start()
        try:
            seen=[]
            while True:
                event=app.events.get(timeout=2);seen.append(event)
                if event[0]=="idle":break
            app.client.stop.assert_called_once_with()
            app.client.command.assert_called_once_with(0x21)
            app.client.status.assert_called_once_with()
            self.assertIn(("message","FPGA 故障已清除；下一次运动仍须人工启动"),seen)
        finally:
            app.shutdown.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

    def test_clear_fault_timeout_keeps_connection_and_marks_result_unknown(self):
        import queue
        app=object.__new__(app_module.App)
        app.shutdown=threading.Event();app.cancel=threading.Event()
        app.jobs=queue.Queue();app.events=queue.Queue();app.lidar_requested=False
        app.client=Mock();app.client.stop.side_effect=TimeoutError("STOP未确认")
        app.cleanup=Mock();app.telemetry=None
        app.jobs.put(("clear",()))
        worker=threading.Thread(target=app.worker,daemon=True);worker.start()
        try:
            seen=[]
            while True:
                event=app.events.get(timeout=2);seen.append(event)
                if event[0]=="idle":break
            self.assertTrue(any(k=="error" and "结果未确认" in v for k,v in seen))
            app.client.command.assert_not_called()
            app.cleanup.assert_not_called()
        finally:
            app.shutdown.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

    def test_telemetry_summary_contains_motion_imu_network_and_video_fields(self):
        from types import SimpleNamespace
        app=object.__new__(app_module.App)
        app.last_console_telemetry=0;app.log_view=Mock();app.log_view.index.return_value="2.0"
        snap=SimpleNamespace(ms=10,seq=2,state=2,faults=0,left_target=100,right_target=100,
            left_speed=90,right_speed=91,left_count=4,right_count=5,left_pwm=200,right_pwm=201,
            yaw_raw=2,gyro_raw=-1,flags=4,network_diagnostics=lambda:{"bridge_state":"RECEIVE","rx_bad_fcs_saturated15":3})
        client=SimpleNamespace(diag=SimpleNamespace(request_id=4,replies=3,requests=4,timeouts=1,rtt_ms=2.5))
        telemetry=SimpleNamespace(diagnostics=lambda:{"scan_gaps":2,"host_bad_packets":1})
        video=SimpleNamespace(assembler=SimpleNamespace(completed=8,dropped=1))
        app.log_telemetry_summary(snap,client,telemetry,video)
        text=app.log_view.insert.call_args.args[1]
        for field in ("TEL", "target=100/100", "speed=90/91", "pwm=200/201", "yaw=2", "badfcs=3", "timeout=1", "lidar_gap=2", "video=8/1"):
            self.assertIn(field,text)

    def test_telemetry_summary_supports_ems1_without_pwm_fields(self):
        from types import SimpleNamespace
        app=object.__new__(app_module.App)
        app.last_console_telemetry=0;app.log_view=Mock();app.log_view.index.return_value="2.0"
        snap=SimpleNamespace(ms=10,seq=2,state=0,faults=0,left_target=0,right_target=0,
            left_speed=0,right_speed=0,left_count=0,right_count=0,yaw_raw=0,gyro_raw=0,flags=4,
            network_diagnostics=lambda:{"bridge_state":"RECEIVE"})
        app.log_telemetry_summary(snap,None,None,None)
        self.assertIn("pwm=NA/NA",app.log_view.insert.call_args.args[1])

    def test_log_persists_level_and_displays_it(self):
        app=object.__new__(app_module.App)
        app.calibration=Mock();app.calibration.data={"revision":74106};app.calibration.digest="digest"
        app.fid=3;app.logfile=Mock();app.log_view=Mock();app.log_view.index.return_value="2.0"
        app.log("warning","temporary timeout")
        payload=app.logfile.write.call_args.args[0]
        self.assertIn('"level": "WARNING"',payload)
        self.assertIn("[WARNING] temporary timeout",app.log_view.insert.call_args.args[1])

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
                self.assertLessEqual(app.diagnostic_label.winfo_rooty()+app.diagnostic_label.winfo_height(),app.camera.master.winfo_rooty()+app.camera.master.winfo_height())
                self.assertFalse(app.connected)
                self.assertIsNone(app.client)
                self.assertEqual(str(app.lidar_start.cget("state")),"disabled")
                app.sensor_tabs.select(app.fusion_view.frame);root.update()
                app.fusion_view.update({"raw":bytes([0x55])*4096,"initial":(0,0,0),"target":(500,300,0)})
                root.update()
                self.assertIsNotNone(app.fusion_view.photo)
                self.assertGreaterEqual(app.fusion_view.canvas.winfo_height(),150)
                self.assertTrue(any(app.fusion_view.canvas.type(item)=="image" for item in app.fusion_view.canvas.find_all()))
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
