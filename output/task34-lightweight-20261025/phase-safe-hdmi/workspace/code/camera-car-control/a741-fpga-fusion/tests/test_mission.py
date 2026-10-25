import struct
import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from fusion import FusionClient,MissionStatus,waypoint_payload
from client import CalibrationRejected


class MissionTests(unittest.TestCase):
    def test_waypoint_encoding_and_invalid_entire_route_before_hardware(self):
        self.assertEqual(waypoint_payload((25,25,90)),struct.pack("<BBH",64,64,16384))
        client=object.__new__(FusionClient)
        client.navigation_status=Mock()
        with self.assertRaises(ValueError):
            client.run_waypoints(None,[(0,0,0),(float("nan"),0,0)],threading.Event(),Mock())
        client.navigation_status.assert_not_called()

    def test_status_decodes_cpu_lease_and_waypoint_progress(self):
        packet=bytearray(32);packet[1]=3;packet[4:8]=bytes([2,5,4,0])
        status=MissionStatus.parse(packet)
        self.assertTrue(status.active);self.assertTrue(status.cpu_alive)
        self.assertEqual((status.index,status.count,status.phase,status.error),(2,5,4,0))

    def fixture(self):
        c=object.__new__(FusionClient)
        c.navigation_status=Mock(return_value=Mock(geometry_verified=True,localized=True,flags=0))
        c.disarm=Mock();c.arm=Mock();c.stop=Mock();c.heartbeat=Mock()
        return c

    def test_upload_start_completion_uses_onboard_lease_and_stops_at_end(self):
        c=self.fixture()
        idle=MissionStatus(False,True,False,0,2,0,0)
        running=MissionStatus(True,True,False,0,2,4,0)
        done=MissionStatus(False,True,False,2,2,0,0)
        polls=iter([running,done])
        c.mission_command=Mock(side_effect=lambda op,*args:next(polls) if op==4 else idle)
        with patch("fusion.time.sleep"):
            result=c.run_waypoints(None,[(25,25,0),(125,25,0)],threading.Event(),Mock())
        self.assertEqual(result,done)
        self.assertEqual([call.args[0] for call in c.mission_command.call_args_list],[0,1,1,2,4,4])
        c.arm.assert_called_once();c.heartbeat.assert_not_called();c.stop.assert_called_once()

    def test_fault_stops_without_retrying_start_or_arm(self):
        c=self.fixture();bad=MissionStatus(False,True,False,0,1,0,4)
        c.mission_command=Mock(return_value=bad)
        with self.assertRaises(CalibrationRejected):
            c.run_waypoints(None,[(25,25,0)],threading.Event(),Mock())
        c.arm.assert_called_once();c.stop.assert_called_once()
        self.assertEqual(sum(call.args[0]==2 for call in c.mission_command.call_args_list),1)

    def test_cancel_before_start_never_arms(self):
        c=self.fixture();c.mission_command=Mock();cancel=threading.Event();cancel.set()
        with self.assertRaises(CalibrationRejected):c.run_waypoints(None,[(25,25,0)],cancel,Mock())
        c.arm.assert_not_called();c.stop.assert_called_once()


if __name__=="__main__":unittest.main()
