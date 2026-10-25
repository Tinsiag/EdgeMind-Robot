import base64
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from calibration import Calibration
from client import CalibrationRejected
from fusion import FusionClient,MapTransport,NavigationStatus,load_map,map_record
from protocol import crc16_ccitt
from fusion_config import compiled_parameters


class FusionTests(unittest.TestCase):
    def test_navigation_layout_and_geometry_lock(self):
        raw=bytearray(32);raw[1:4]=bytes([2,3,0x88]);struct.pack_into("<iihHI",raw,4,-50,125,-16384,600,9);raw[20]=82
        struct.pack_into("<HH",raw,22,12,99)
        status=NavigationStatus.parse(raw)
        self.assertEqual((status.x_mm,status.y_mm,status.yaw_raw,status.front_mm,status.map_revision),(-50,125,-16384,600,9))
        self.assertTrue(status.geometry_verified);self.assertTrue(status.localized)
        self.assertEqual((status.remaining,status.expanded),(12,99))
        raw[0]=1
        with self.assertRaises(ValueError):NavigationStatus.parse(raw)

    def test_map_export_roundtrip_crc_and_old_map_rejection(self):
        raw=bytes(range(256))*16;record=map_record(raw,Calibration.load(),{"navigation_geometry_verified":False})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"map.json";path.write_text(json.dumps(record))
            self.assertEqual(load_map(path),raw)
            record["crc32"]^=1;path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):load_map(path)
            path.write_text('{"format":"CoreSLAM"}')
            with self.assertRaises(ValueError):load_map(path)

    def test_map_socket_validates_crc_id_source_and_never_sends_motion(self):
        sock=Mock();transport=object.__new__(MapTransport);transport.socket=sock;transport.peer=("192.168.0.2",6104);transport.number=40
        payload=bytes(32);body=struct.pack("<4sIBB",b"EMM1",41,0xd0,32)+payload
        response=body+struct.pack("<H",crc16_ccitt(body))
        sock.recvfrom.side_effect=[(response[:-1]+bytes([response[-1]^1]),transport.peer),(response,transport.peer)]
        self.assertEqual(transport.command(0x51,b"\0\0\0\1"),payload)
        data,peer=sock.sendto.call_args.args
        self.assertEqual(peer,transport.peer);self.assertEqual(data[:4],b"EMM1");self.assertEqual(data[8],0x51)
        for cmd in (2,0x11,0x42,0x55):
            with self.assertRaises(ValueError):transport.command(cmd)
        self.assertEqual(sock.sendto.call_count,1)

    def test_locked_navigation_never_arms(self):
        c=object.__new__(FusionClient);c.navigation_status=Mock(return_value=Mock(geometry_verified=False,localized=True));c.arm=Mock()
        with self.assertRaises(CalibrationRejected):c.navigate(Calibration.load(),threading.Event(),lambda:True,Mock())
        c.arm.assert_not_called()

    def test_upload_cancel_never_commits(self):
        c=object.__new__(FusionClient);c.map_begin=Mock();c.map_commit=Mock();c.fusion_command=Mock();c.heartbeat=Mock()
        cancel=threading.Event();cancel.set()
        with self.assertRaises(CalibrationRejected):c.upload_map(bytes(4096),cancel)
        c.map_commit.assert_not_called();c.fusion_command.assert_not_called()

    def test_map_upload_sends_exact_crc_and_bounded_chunks(self):
        c=object.__new__(FusionClient);c.map_begin=Mock();c.map_commit=Mock(return_value=zlib.crc32(bytes([0x55])*4096));c.fusion_command=Mock();c.heartbeat=Mock()
        raw=bytes([0x55])*4096;c.upload_map(raw,threading.Event())
        c.map_commit.assert_called_once_with(zlib.crc32(raw))
        rebuilt=bytearray()
        for call in c.fusion_command.call_args_list:
            kind,p=call.args;self.assertEqual(kind,0x51);op,address,size=struct.unpack_from("<BHB",p)
            self.assertEqual(address,len(rebuilt));self.assertEqual(op,1);self.assertLessEqual(size,24);self.assertEqual(len(p),size+4);rebuilt.extend(p[4:])
        self.assertEqual(rebuilt,raw)

    def test_goal_bounds_fail_before_transmission(self):
        c=object.__new__(FusionClient);c.fusion_command=Mock()
        for args in ((3200,0,0),(0,float('nan'),0),(0,0,float('inf'))):
            with self.assertRaises(ValueError):c.goal(*args)
        c.fusion_command.assert_not_called()

    def test_navigate_ui_stall_stops_without_retry(self):
        c=object.__new__(FusionClient);c.navigation_status=Mock(return_value=Mock(geometry_verified=True,localized=True,flags=0));c.arm=Mock();c.stop=Mock();c.fusion_command=Mock();c.prepare_lidar=Mock()
        with self.assertRaises(CalibrationRejected):c.navigate(Calibration.load(),threading.Event(),lambda:False,Mock())
        c.fusion_command.assert_called_once_with(0x55);c.stop.assert_called_once()

    def test_geometry_identity_tracks_offsets_and_refuses_incomplete_verification(self):
        geometry=json.loads((Path(__file__).resolve().parents[1]/"config/geometry.json").read_text(encoding="utf-8"))
        calibration=dict(Calibration.load().data)
        values,crc=compiled_parameters(geometry,calibration)
        self.assertEqual(values["GEOMETRY_VERIFIED"],1)
        self.assertGreaterEqual(values["RADIUS_MM"],250)
        self.assertEqual(values["LIDAR_X"],164)
        self.assertGreaterEqual(values["HALF_WIDTH"],131)
        calibration["lidar_zero_offset_deg"]+=1
        self.assertNotEqual(compiled_parameters(geometry,calibration)[1],crc)
        geometry["vehicle_outer_footprint_mm"]=None
        with self.assertRaises(ValueError):compiled_parameters(geometry,calibration)

    def test_configuration_mismatch_never_prepares_lidar_or_arms(self):
        c=object.__new__(FusionClient);c.fusion_enabled=True;c.prepare_lidar=Mock()
        c.compiled_geometry=json.loads((Path(__file__).resolve().parents[1]/"config/geometry.json").read_text(encoding="utf-8"))
        _,crc=compiled_parameters(c.compiled_geometry,Calibration.load().data)
        c.navigation_status=Mock(return_value=Mock(config_crc=crc^1))
        with self.assertRaises(CalibrationRejected):c.arm(Calibration.load())
        c.prepare_lidar.assert_not_called()

if __name__=="__main__":unittest.main()
