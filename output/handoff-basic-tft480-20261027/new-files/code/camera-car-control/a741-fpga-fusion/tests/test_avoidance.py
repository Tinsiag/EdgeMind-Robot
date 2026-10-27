import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"host"))
from avoidance import AvoidanceClient,AvoidanceStatus
from client import CalibrationRejected
from board_config import compiled_parameters


class AvoidanceTests(unittest.TestCase):
    def test_wire_status_is_basic_not_old_navigation(self):
        data=bytearray(32);data[1]=2;data[3]=0x87
        struct.pack_into("<hHHH",data,12,-100,450,800,600)
        data[20]=1;struct.pack_into("<II",data,22,1234,0x12345678);data[30:32]=b"\x01\x01"
        struct.pack_into("<hh",data,4,-32768,32767)
        status=AvoidanceStatus.parse(data)
        self.assertTrue(status.active)
        self.assertEqual((status.front_mm,status.left_mm,status.right_mm),(450,800,600))
        self.assertEqual((status.uptime_ms,status.config_crc),(1234,0x12345678))
        self.assertEqual((status.roll_raw,status.pitch_raw),(-32768,32767))
        data[31]=0
        with self.assertRaises(CalibrationRejected):AvoidanceStatus.parse(data)

    def test_start_stop_send_only_explicit_single_byte_commands(self):
        client=object.__new__(AvoidanceClient);client.avoidance_enabled=True
        client.command=Mock(return_value=bytes(32));client.arm=Mock()
        client.start_avoidance();client.command.assert_called_once_with(0x59,b"\x01",reply=0xd0)
        client.arm.assert_not_called()
        client.command.reset_mock();client.stop_avoidance()
        client.command.assert_called_once_with(0x59,b"\x00",reply=0xd0)

    def test_sensor_only_start_and_unsupported_firmware_never_send(self):
        client=object.__new__(AvoidanceClient);client.command=Mock();client.sensors_only=True
        with self.assertRaises(CalibrationRejected):client.start_avoidance()
        client.sensors_only=False;client.avoidance_enabled=False
        with self.assertRaises(CalibrationRejected):client.start_avoidance()
        client.command.assert_not_called()

    def test_cad_identity_keeps_physical_validation_separate(self):
        geometry=json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8"))
        calibration=json.loads((ROOT/"config/calibration.json").read_text(encoding="utf-8"))
        values,crc=compiled_parameters(geometry,calibration)
        self.assertEqual(values["RADIUS_MM"],257)
        self.assertFalse(geometry["physical_geometry_verified"])
        altered=dict(calibration,mechanical_track_um=250000)
        with self.assertRaises(ValueError):compiled_parameters(geometry,altered)
        self.assertIsInstance(crc,int)


if __name__=="__main__":unittest.main()
