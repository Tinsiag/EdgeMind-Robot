import queue
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock,patch
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from app import App,service_action,status_text
from avoidance import AvoidanceStatus


class GuiTests(unittest.TestCase):
    def test_connect_never_calibrates_arms_or_starts(self):
        c=Mock();cal=Mock()
        service_action(c,cal,"connect",threading.Event())
        c.connect.assert_called_once_with(cal)
        c.arm.assert_not_called();c.start_avoidance.assert_not_called();c.calibrate.assert_not_called()

    def test_stop_and_disarm_win_over_cancel(self):
        c=Mock();cancel=threading.Event();cancel.set()
        service_action(c,Mock(),"stop",cancel)
        self.assertEqual([call[0] for call in c.method_calls],["stop","disarm"])

    def test_cancelled_start_never_reaches_fpga(self):
        c=Mock();cancel=threading.Event();cancel.set()
        with self.assertRaises(RuntimeError):service_action(c,Mock(),"start",cancel)
        c.start_avoidance.assert_not_called()

    def test_sensors_only_rejects_arm_and_start(self):
        for action in ("arm","start"):
            c=Mock()
            with self.assertRaises(RuntimeError):service_action(c,Mock(),action,threading.Event(),True)
            c.arm.assert_not_called();c.start_avoidance.assert_not_called()

    def test_clear_fault_verifies_fpga_before_success(self):
        c=Mock();c.status.return_value.faults=4
        with self.assertRaises(RuntimeError):service_action(c,Mock(),"clear",threading.Event())
        c.stop.assert_called_once();c.disarm.assert_called_once();c.status.assert_called_once()

    def test_stop_discards_a_queued_start(self):
        app=object.__new__(App);app.cancel=threading.Event();app.jobs=queue.Queue(maxsize=1)
        app.action_lock=threading.Lock();app.stop_epoch=0;app.stop_pending=False;app.busy=True
        app.peer=Mock();app.peer.get.return_value="192.168.0.2"
        app.jobs.put(("start","192.168.0.2"));app.stop()
        self.assertTrue(app.cancel.is_set());self.assertEqual(app.jobs.get_nowait()[0],"stop")
        self.assertTrue(app.jobs.empty())

    def test_arm_is_explicit_separate_from_start(self):
        c=Mock();cal=Mock();service_action(c,cal,"arm",threading.Event())
        c.arm.assert_called_once_with(cal);c.start_avoidance.assert_not_called()

    def test_pending_stop_cannot_be_cleared_by_submit(self):
        app=object.__new__(App);app.cancel=threading.Event();app.jobs=queue.Queue(maxsize=1)
        app.action_lock=threading.Lock();app.stop_epoch=0;app.stop_pending=False;app.busy=True
        app.sensors_only=False;app.peer=Mock();app.message=Mock()
        app.stop();app.submit("start")
        self.assertTrue(app.cancel.is_set())
        self.assertEqual(app.jobs.get_nowait()[0],"stop")
        self.assertTrue(app.jobs.empty())

    def test_stop_timeout_still_attempts_disarm(self):
        c=Mock();c.stop.side_effect=TimeoutError("lost")
        with self.assertRaises(TimeoutError):service_action(c,Mock(),"stop",threading.Event())
        c.disarm.assert_called_once()

    def test_tilt_and_yaw_validity_are_independent(self):
        for flags in (0,0x20,0x40,0x60):
            s=AvoidanceStatus(0,0,flags,1234,10,20,30,1,10,20,8192,-4096)
            text=status_text(s,None,1)
            self.assertEqual("ROLL / PITCH 无效" in text,not bool(flags&0x20))
            self.assertEqual("YAW 无效" in text,not bool(flags&0x40))
            self.assertIn("雷达数据无效",text)
            self.assertIn("电机故障遥测已过期",text)

    def test_disconnect_and_status_timeout_remove_old_values(self):
        app=object.__new__(App);app.events=queue.Queue();app.closed=threading.Event()
        app.closed.set();app.status=Mock();app.message=Mock();app.last_status=0
        app.poll();self.assertIn("过期",app.status.set.call_args.args[0])
        app.events.put(("disconnected",None));app.poll()
        self.assertIsNone(app.last_status)
        self.assertIn("状态未知",app.status.set.call_args.args[0])

    def worker_app(self):
        app=object.__new__(App);app.action_lock=threading.Lock();app.cancel=threading.Event()
        app.closed=Mock();app.closed.is_set.return_value=False;app.closed.wait.side_effect=[False,True]
        app.jobs=queue.Queue(maxsize=1);app.jobs.put(("connect","192.168.0.2",0))
        app.events=queue.Queue();app.calibration=Mock();app.stop_epoch=0
        app.busy=True;app.stop_pending=False;app.sensors_only=True;app.ui_seen=time.monotonic()
        return app

    def test_rejected_connect_closes_socket_and_never_keeps_lease_alive(self):
        app=self.worker_app();client=Mock();client.connect.side_effect=ValueError("wrong CRC")
        with patch("app.AvoidanceClient",return_value=client),patch("app.TelemetryReceiver") as receiver:
            app.worker()
        client.close.assert_called_once();client.heartbeat.assert_not_called();receiver.assert_not_called()
        self.assertTrue(client.sensors_only)

    def test_stalled_ui_stops_heartbeat_and_closes_both_receivers(self):
        app=self.worker_app();app.closed.wait.side_effect=[False,False,True]
        client=Mock();telemetry=Mock();telemetry.read.return_value=(None,())
        def ui_stalls():app.ui_seen=0
        client.heartbeat.side_effect=ui_stalls
        with patch("app.AvoidanceClient",return_value=client),patch("app.TelemetryReceiver",return_value=telemetry):
            app.worker()
        client.heartbeat.assert_called_once();client.close.assert_called_once();telemetry.close.assert_called_once()
        client.stop.assert_called_once();client.disarm.assert_called_once()


if __name__=="__main__":unittest.main()
