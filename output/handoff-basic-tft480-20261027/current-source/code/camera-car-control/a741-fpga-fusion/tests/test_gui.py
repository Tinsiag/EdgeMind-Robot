import queue
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from app import App,service_action


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
        app.peer=Mock();app.peer.get.return_value="192.168.0.2"
        app.jobs.put(("start","192.168.0.2"));app.stop()
        self.assertTrue(app.cancel.is_set());self.assertEqual(app.jobs.get_nowait()[0],"stop")
        self.assertTrue(app.jobs.empty())

    def test_arm_is_explicit_separate_from_start(self):
        c=Mock();cal=Mock();service_action(c,cal,"arm",threading.Event())
        c.arm.assert_called_once_with(cal);c.start_avoidance.assert_not_called()


if __name__=="__main__":unittest.main()
