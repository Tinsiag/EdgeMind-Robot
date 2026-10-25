import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import struct
import sys
import unittest
import threading
import time
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from calibration import Calibration
from telemetry import ScanAssembler, Snapshot, TelemetryReceiver, crc8, lidar_points
import client


def packet(start, end, seq=1, stamp=0):
    raw = bytearray(47)
    raw[:2] = b"\x54\x2c"
    struct.pack_into("<H", raw, 4, start)
    for i in range(12):
        struct.pack_into("<HB", raw, 6+3*i, 1000, 100)
    struct.pack_into("<H", raw, 42, end)
    raw[-1] = crc8(raw[:-1])
    return struct.pack("<4sHHII", b"EML1", 1, 64, seq, stamp)+raw+b"\0"


class HostTests(unittest.TestCase):
    def test_held_drive_keeps_heartbeats_without_udp_status_polls(self):
        pivot = math.degrees(2000*200/Calibration.load().data["mechanical_track_um"])
        for linear, angular in ((200, 0), (-200, 0), (150, 30), (0, pivot), (0, -pivot)):
            clock = [0.0]
            beats = []
            c = object.__new__(client.Client);c.imu_motion = True
            c.arm = Mock();c.wheels = Mock();c.command = Mock();c.stop = Mock()
            c.status = Mock(side_effect=AssertionError("blocking status poll"))
            c.sensors = Mock(side_effect=AssertionError("blocking IMU poll"))
            c.settle = Mock(return_value="stopped")
            receiver = Mock()
            receiver.read.side_effect = lambda: (self.distance_snapshot(1000+round(clock[0]*1000)), ())
            def heartbeat():
                beats.append(clock[0])
                if clock[0] >= 1:
                    held.clear()
            def sleep(seconds):
                clock[0] += seconds
                held.renew()
            c.heartbeat = Mock(side_effect=heartbeat)
            with patch.object(client.time, "monotonic", side_effect=lambda: clock[0]), patch.object(client.time, "sleep", side_effect=sleep):
                held = client.HoldLease();held.set()
                result = c.drive(Calibration.load(), linear, angular, held, threading.Event(), telemetry=receiver)
            self.assertGreaterEqual(result["drive_seconds"], 1)
            self.assertGreater(len(beats), 20)
            self.assertLess(max(b-a for a, b in zip(beats, beats[1:])), .05)
            c.status.assert_not_called();c.sensors.assert_not_called()
            c.arm.assert_called_once();c.settle.assert_called_once()
            if linear == 0:
                self.assertGreater(c.command.call_count, 20)
                for call in c.command.call_args_list:
                    self.assertEqual(call.args[0], 0x47)
                    left, right, _ = struct.unpack("<iih", call.args[1])
                    self.assertEqual((left, right), (-200, 200) if angular > 0 else (200, -200))
                    self.assertIsNone(call.kwargs["reply"])

    def test_held_drive_stale_telemetry_stops_before_or_during_motion(self):
        for samples in ([None], [self.distance_snapshot(1000), None]):
            c = object.__new__(client.Client)
            c.arm = Mock();c.wheels = Mock();c.stop = Mock();c.heartbeat = Mock()
            receiver = Mock();receiver.read.side_effect = [(sample, ()) for sample in samples]
            held = threading.Event();held.set()
            with self.assertRaisesRegex(client.CalibrationRejected, "遥测.*150ms"):
                c.drive(Calibration.load(), 200, 0, held, threading.Event(), telemetry=receiver)
            c.stop.assert_called_once()
            self.assertEqual(c.arm.call_count, len(samples)-1)
            self.assertEqual(c.wheels.call_count, len(samples)-1)

    def test_held_drive_retains_latched_fault_without_retry_or_clear(self):
        c = object.__new__(client.Client)
        c.arm = Mock();c.wheels = Mock();c.stop = Mock();c.heartbeat = Mock();c.command = Mock()
        snapshot = self.distance_snapshot(1000)
        receiver = Mock();receiver.read.side_effect = [(snapshot, ()), (replace(snapshot, state=3, faults=1), ())]
        held = threading.Event();held.set()
        with self.assertRaisesRegex(client.CalibrationRejected, "0x0001"):
            c.drive(Calibration.load(), 200, 0, held, threading.Event(), telemetry=receiver)
        c.arm.assert_called_once();c.wheels.assert_called_once();c.command.assert_not_called()

    def test_held_drive_tolerates_only_initial_telemetry_state_delay(self):
        c = object.__new__(client.Client)
        c.arm = Mock();c.wheels = Mock();c.stop = Mock();c.heartbeat = Mock();c.settle = Mock(return_value="stopped")
        idle = replace(self.distance_snapshot(1000), state=0)
        held = threading.Event();held.set()
        receiver = Mock();receiver.read.side_effect = [(idle, ()), (idle, ())]
        def released(_):
            held.clear()
        with patch.object(client.time, "sleep", side_effect=released):
            result = c.drive(Calibration.load(), 200, 0, held, threading.Event(), telemetry=receiver)
        self.assertEqual(result["final_status"], "stopped")
        receiver.read.side_effect = None;receiver.read.return_value = (idle, ())
        held.set()
        with patch.object(client.time, "monotonic", side_effect=[10, 10, 10.151]):
            with self.assertRaisesRegex(client.CalibrationRejected, "state=0"):
                c.drive(Calibration.load(), 200, 0, held, threading.Event(), telemetry=receiver)

    def test_settle_uses_live_telemetry_while_renewing_lease(self):
        clock = [0.0]
        c = object.__new__(client.Client)
        c.wheels = Mock();c.heartbeat = Mock();c.disarm = Mock(return_value="stopped")
        c.status = Mock(side_effect=AssertionError("blocking stop status poll"))
        receiver = Mock();receiver.read.return_value = (replace(self.distance_snapshot(1000), state=1), ())
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(client.time, "monotonic", side_effect=lambda: clock[0]), patch.object(client.time, "sleep", side_effect=sleep):
            result = c.settle(telemetry=receiver)
        self.assertEqual(result, "stopped")
        c.wheels.assert_called_once_with(0, 0);c.disarm.assert_called_once();c.status.assert_not_called()
        self.assertGreaterEqual(c.heartbeat.call_count, 10)

    @staticmethod
    def distance_snapshot(ms, count=0):
        data = bytearray(112)
        struct.pack_into("<4sHHIIIHBBH", data, 0, b"EMS1", 1, 112,
                         ms, ms, 74106, 0x13, 2, 0, 0)
        struct.pack_into("<iiiiii", data, 28, 100, 100, 0, 0, count, count)
        return Snapshot.parse(data)

    def test_distance_uses_atomic_telemetry_in_both_directions_without_control_polls(self):
        from types import SimpleNamespace
        for sign in (1, -1):
            c = object.__new__(client.Client)
            c.arm = Mock();c.heartbeat = Mock();c.wheels = Mock();c.stop = Mock()
            c.status = Mock(side_effect=AssertionError("status poll delays the heading loop"))
            c.sensors = Mock(side_effect=AssertionError("sensor poll delays the heading loop"))
            c.settle = Mock(return_value=SimpleNamespace(left_count=sign*350, right_count=sign*350))
            receiver = Mock()
            receiver.read.side_effect = [(self.distance_snapshot(1000), ()),
                                        (self.distance_snapshot(1050), ()),
                                        (self.distance_snapshot(1100, sign*350), ())]
            with patch.object(client.time, "sleep"):
                result = c.distance(Calibration.load(), sign*50, 100, threading.Event(), telemetry=receiver)
            c.wheels.assert_called_once_with(sign*100, sign*100, hold=False)
            c.status.assert_not_called();c.sensors.assert_not_called()
            self.assertLess(abs(result["encoder_error_mm"]), 1)

    def test_distance_stale_telemetry_stops_without_wheel_command(self):
        c = object.__new__(client.Client)
        c.arm = Mock();c.stop = Mock();c.wheels = Mock()
        receiver = Mock();receiver.read.return_value = (None, ())
        with self.assertRaisesRegex(client.CalibrationRejected, "遥测.*150ms"):
            c.distance(Calibration.load(), 50, 100, threading.Event(), telemetry=receiver)
        c.stop.assert_called_once();c.wheels.assert_not_called()

    def test_distance_telemetry_keeps_heading_gap_protection(self):
        c = object.__new__(client.Client)
        c.arm = Mock();c.stop = Mock();c.wheels = Mock();c.heartbeat = Mock()
        receiver = Mock()
        receiver.read.side_effect = [(self.distance_snapshot(1000), ()),
                                    (self.distance_snapshot(1050), ()),
                                    (self.distance_snapshot(1251), ())]
        with patch.object(client.time, "sleep"):
            with self.assertRaisesRegex(client.CalibrationRejected, "150ms"):
                c.distance(Calibration.load(), 50, 100, threading.Event(), telemetry=receiver)
        c.stop.assert_called_once();c.wheels.assert_called_once()

    def test_telemetry_diagnostics_remain_available_after_disconnect(self):
        receiver = TelemetryReceiver(peer="127.0.0.1", port=0)
        try:
            before = receiver.diagnostics()
        finally:
            receiver.close()
        after = receiver.diagnostics()
        self.assertGreater(before["receive_buffer_bytes"], 0)
        self.assertEqual(after, before)
        self.assertFalse(receiver.thread.is_alive())

    def test_uncalibrated_arm_rejection_explains_calibration_without_retry(self):
        c=object.__new__(client.Client)
        c.imu_test=False;c.motion_lidar=True;c.sensor_pins_enabled=False
        c.command=Mock(return_value=b"status")
        c.sensors=Mock(return_value={"flags":0,"valid":3})
        with patch.object(client,"decode_status",return_value=Mock(state=0,faults=0)):
            with self.assertRaisesRegex(client.CalibrationRejected,"静止校准"):
                c.arm(Calibration.load())
        c.command.assert_called_once_with(2)

    def test_latched_fault_arm_rejection_is_recoverable_and_never_clears_fault(self):
        c=object.__new__(client.Client)
        c.imu_test=False;c.motion_lidar=True;c.sensor_pins_enabled=False
        c.command=Mock(return_value=b"status")
        for faults, message in ((4, "编码器无反馈故障"), (1, "通信超时故障.*清除故障")):
            c.command.reset_mock()
            with patch.object(client,"decode_status",return_value=Mock(state=3,faults=faults)):
                with self.assertRaisesRegex(client.CalibrationRejected,message):
                    c.arm(Calibration.load())
            c.command.assert_called_once_with(2)

    def test_arc_reference_scaled_signed_and_wrapped(self):
        calibration=Calibration.load()
        for sign in (1,-1):
            d=copy.deepcopy(calibration.data);d["imu_yaw_sign"]=sign
            cfg=Calibration(d)
            held=threading.Event();held.set()
            c=object.__new__(client.Client);c.imu_motion=True
            c.sensors=Mock(return_value={"yaw":32700})
            c.arm=Mock();c.heartbeat=Mock()
            c.status=Mock(return_value=Mock(faults=0,state=2))
            c.settle=Mock(return_value="stopped")
            c.command=Mock(side_effect=lambda *a,**k: held.clear())
            with patch.object(client.time,"monotonic",side_effect=[10,11,11.1]),patch.object(client.time,"sleep"):
                result=c.drive(cfg,200,180,held,threading.Event())
                self.assertEqual(result["final_status"],"stopped")
                self.assertEqual(result["stop_reason"],"released")
                self.assertEqual(result["drive_seconds"],1.1)
            args=c.command.call_args
            self.assertEqual(args.args[0],0x47)
            left,right,reference=struct.unpack("<iih",args.args[1])
            self.assertEqual((left,right),cfg.arc(200,180))
            half=__import__("math").radians(180)*234000/2000
            scale=max(1,(200+half)/cfg.data["max_speed_mm_s"])
            expected=(round(32700+sign*180/scale*65536/360)+32768)%65536-32768
            self.assertEqual(reference,expected)
            self.assertIsNone(args.kwargs["reply"])

    def test_arc_runtime_encoder_fault_is_recoverable_not_transport_failure(self):
        cfg=Calibration.load()
        held=threading.Event();held.set()
        c=object.__new__(client.Client);c.imu_motion=True
        c.sensors=Mock(return_value={"yaw":0})
        c.arm=Mock();c.heartbeat=Mock();c.wheels=Mock();c.command=Mock()
        c.status=Mock(return_value=Mock(faults=4,state=3))
        with self.assertRaisesRegex(client.CalibrationRejected,"连接保持"):
            c.drive(cfg,100,30,held,threading.Event())
        c.arm.assert_called_once()

    def test_phy_diagnostic_layout_does_not_touch_scan(self):
        receiver=object.__new__(TelemetryReceiver)
        receiver.bytes=0;receiver.errors=0
        data=bytearray(32)
        struct.pack_into("<4sHHII",data,0,b"EMP1",1,32,123,456)
        struct.pack_into("<IHHH",data,16,0x001cc916,0x1140,0x7949,0x796d)
        data[26:32]=bytes((1,0,0,5,50,10))
        receiver.ingest(data)
        self.assertEqual(receiver.phy_diagnostic["identity"],0x001cc916)
        self.assertEqual(receiver.phy_diagnostic["bmcr"],0x1140)
        self.assertEqual(receiver.phy_diagnostic["bmsr_current"],0x796d)
        self.assertEqual(receiver.phy_diagnostic["settle_ms"],50)
        self.assertEqual(receiver.phy_diagnostic["reset_ms"],10)
        self.assertTrue(receiver.phy_diagnostic["ready"])
        self.assertEqual(receiver.errors,0)
        receiver.ingest(data[:-1])
        self.assertEqual(receiver.errors,1)

    def test_sensor_debug_blocks_motor_packets_before_socket_access(self):
        c=object.__new__(client.Client);c.sensors_only=True
        for kind in (2,0x11,0x42,0x45):
            with self.assertRaisesRegex(ValueError,"禁止ARM"):
                c.command(kind)

    def test_front_left_raw_rotation_maps_to_forward_for_a741(self):
        from app import lidar_display_angle
        calibration=Calibration.load()
        self.assertEqual(calibration.data["lidar_zero_offset_deg"],270)
        self.assertAlmostEqual(lidar_display_angle(27000,calibration.data),0)
        self.assertAlmostEqual(lidar_display_angle(0,calibration.data),270)

    def test_mapping_pairing_rejects_stale_and_marks_packet_gaps(self):
        receiver=object.__new__(TelemetryReceiver)
        receiver.lock=threading.Lock()
        receiver.bytes=0;receiver.errors=0;receiver.snapshot=None;receiver.updated=None
        receiver.history=__import__("collections").deque(maxlen=100)
        receiver.scan=ScanAssembler();receiver.mapping_queue=__import__("collections").deque(maxlen=3)
        receiver.mapping_dropped=0
        data=bytearray(112)
        struct.pack_into("<4sHHIIIHBBH",data,0,b"EMS1",1,112,1,240,74103,0x11,0,0,0)
        base=time.monotonic()
        receiver.ingest(bytes(data),now=base)
        for seq,angle in enumerate(range(0,72000,3000),1):
            receiver.ingest(packet(angle%36000,(angle+3000)%36000,seq,seq*10),now=base+seq*.002)
        samples=receiver.mapping_samples()
        self.assertTrue(any(sample[0] is not None for sample in samples))
        receiver.ingest(packet(100,200,100,130),now=base+.1)
        invalid=next(sample for sample in receiver.mapping_samples() if sample[0] is None)
        self.assertIn("序号缺口",invalid[4])
        receiver.mapping_queue.clear()
        receiver.queue_mapping((9,240,((0,1000,100),),receiver.snapshot),base-1)
        self.assertEqual(receiver.mapping_samples(),[(None,None,(),None,"上位机处理队列中扫描已过期")])
        receiver.mapping_queue.clear()
        for number in range(5):
            receiver.queue_mapping((number,240,((0,1000,100),),receiver.snapshot),base)
        self.assertGreater(receiver.mapping_dropped,0)
        overflow=next(sample for sample in receiver.mapping_samples() if sample[0] is None)
        self.assertIn("积压",overflow[4])

    def test_expired_visible_scan_freezes_mapping(self):
        receiver=object.__new__(TelemetryReceiver)
        receiver.lock=threading.Lock();receiver.snapshot=None;receiver.updated=None
        receiver.scan=ScanAssembler();receiver.mapping_queue=__import__("collections").deque(maxlen=3)
        receiver.mapping_dropped=0
        receiver.scan.points=[(0,1000,100)];receiver.scan.completed_at=1;receiver.scan.received=1
        receiver.scan.last_angle=100
        self.assertEqual(receiver.read(),(None,()))
        self.assertIn("断流",receiver.mapping_samples()[0][4])
        discontinuities=receiver.scan.discontinuities
        receiver.read()
        self.assertEqual(receiver.scan.discontinuities,discontinuities)
        self.assertFalse(receiver.mapping_samples())

    def test_unmeasured_track_blocks_arc(self):
        data=copy.deepcopy(Calibration.load().data);data["mechanical_track_um"]=None
        c = Calibration(data)
        with self.assertRaises(ValueError):
            c.arc(100, 30)
        self.assertIsNone(c.values(False)[4])
        with self.assertRaises(ValueError):
            c.require_hardware()

    def test_user_measured_track_and_motion_lidar_arm(self):
        config=Calibration.load()
        self.assertEqual(config.data["mechanical_track_um"],234000)
        c=object.__new__(client.Client);c.imu_test=False;c.motion_lidar=True;c.sensor_pins_enabled=False
        c.command=Mock(return_value=bytes([1])+bytes(24))
        c.arm(config)
        c.command.assert_called_once_with(2)

    def test_radar_display_poll_does_not_reset_incomplete_revolution(self):
        scan=ScanAssembler()
        for seq,angle in enumerate(range(0,108000,1000),1):
            scan.feed(packet(angle%36000,(angle+1000)%36000,seq,seq),now=seq*.001)
            scan.visible(seq*.001)
        self.assertGreater(scan.completed_id,0)
        self.assertTrue(scan.visible(.109))
        self.assertIsNotNone(scan.completed_stamp)

    def test_geometry_preserves_ratio(self):
        d = copy.deepcopy(Calibration.load().data)
        d["mechanical_track_um"] = 120000
        c = Calibration(d)
        left, right = c.arc(300, 90)
        self.assertLess(left, right)
        self.assertEqual(right, 394)
        self.assertAlmostEqual(left/right, (300-94.2478)/(300+94.2478), delta=.01)
        self.assertAlmostEqual(c.distance_mm(1469, 1471)[0], 66.3*3.14159265, places=4)

    def test_lidar_crc_and_wrap(self):
        p = packet(35900, 100)
        pts = lidar_points(p[16:63])
        self.assertEqual(pts[0][0], 35900)
        self.assertEqual(pts[-1][0], 100)
        corrupt = bytearray(p[16:63]);corrupt[7] ^= 1
        with self.assertRaises(ValueError):
            lidar_points(corrupt)

    def test_scan_complete_gap_and_stale(self):
        scan = ScanAssembler()
        seq = 1
        for angle in range(0, 72000, 3000):
            scan.feed(packet(angle % 36000, (angle+3000) % 36000, seq, seq*10), now=seq*.005)
            seq += 1
        self.assertTrue(scan.visible(.13))
        scan.feed(packet(100, 200, seq+2, 260), now=.14)
        self.assertFalse(scan.visible(.14))
        self.assertEqual(scan.gaps, 1)
        scan.points = [(0, 100, 100)]
        self.assertFalse(scan.visible(1))

    def test_snapshot_offsets(self):
        p = bytearray(112)
        struct.pack_into("<4sHHIIIHBBH", p, 0, b"EMS1", 1, 112, 1, 100, 74101, 7, 2, 0, 32)
        struct.pack_into("<iiiiii", p, 28, 100, 100, 90, 95, -20, 20)
        struct.pack_into("<hhHHHH", p, 52, -32000, -12, 450, 500, 600, 700)
        s = Snapshot.parse(p)
        self.assertEqual((s.yaw_raw, s.tof_mm, s.left_count, s.faults), (-32000, 450, -20, 32))
        with self.assertRaises(ValueError):
            Snapshot.parse(p[:-1])

    def test_network_diagnostics_preserve_old_snapshot_schema(self):
        p=bytearray(112)
        struct.pack_into("<4sHHIIIHBBH",p,0,b"EMS1",1,112,1,100,74104,0,0,0,0)
        struct.pack_into("<H",p,26,0xa6f3)
        self.assertEqual(Snapshot.parse(p).network_diagnostics(),{"supported":False})
        struct.pack_into("<H",p,20,0x8000)
        self.assertEqual(Snapshot.parse(p).network_diagnostics(),
            {"supported":True,"rx_good_mod16":3,"rx_bad_fcs_saturated15":15,
             "bridge_state":"REPLY","rejected_mod16":10})

    def test_no_motion_retry(self):
        class Silent:
            sent = 0
            def settimeout(self, _): pass
            def sendto(self, *_): self.sent += 1
            def recvfrom(self, *_): raise __import__("socket").timeout()
        c = object.__new__(client.Client)
        c.socket = Silent();c.seq = 0;c.session = 1;c.peer = ("192.168.0.2", 5000)
        c.diag = client.Diagnostics();c.timeout = .001
        with self.assertRaises(TimeoutError):
            c.command(0x42, b"123456")
        self.assertEqual(c.socket.sent, 1)
        self.assertEqual(c.diag.timeouts, 1)

    def test_idempotent_control_retry_is_bounded_and_motion_is_never_retryable(self):
        c=object.__new__(client.Client);c.diag=client.Diagnostics()
        c.command=Mock(side_effect=[TimeoutError("lost"),b"status"])
        self.assertEqual(c.command_idempotent(4),b"status")
        self.assertEqual(c.command.call_count,2)
        self.assertEqual(c.diag.retries,1)
        c.command=Mock(side_effect=TimeoutError("lost twice"))
        with self.assertRaisesRegex(TimeoutError,"lost twice"):
            c.command_idempotent(4)
        self.assertEqual(c.command.call_count,2)
        for kind in (2,0x11,0x42,0x43,0x45,0x46):
            with self.assertRaisesRegex(ValueError,"不允许自动重试"):
                c.command_idempotent(kind)

    def test_old_jy901_firmware_rejected_before_config_write(self):
        c = object.__new__(client.Client)
        c.stop = Mock()
        c.command = Mock(side_effect=[
            b"EVM1"+struct.pack("<HH", 0x11, 400),
            struct.pack("<III", 12, 115200, 74101)])
        with self.assertRaisesRegex(ValueError, "MPU6050"):
            c.connect(Calibration.load())
        self.assertEqual([call.args[0] for call in c.command.call_args_list], [0x40, 0x44])

    def test_imu_test_capability_and_motor_rejection(self):
        c = object.__new__(client.Client)
        c.stop = Mock(); c.status = Mock(return_value="disarmed")
        config = Calibration.load()
        replies = [b"EVM1"+struct.pack("<HH", 0xd1, 400), struct.pack("<III", 12, 6050, 74102)]
        for key, value in enumerate(config.values(require_track=False)):
            if value is not None:
                replies.extend([b"", struct.pack("<III", key, value, 74102)])
        c.command = Mock(side_effect=replies)
        self.assertEqual(c.connect(config), "disarmed")
        self.assertTrue(c.imu_test)
        self.assertFalse(c.sensor_pins_enabled)
        c.command.reset_mock()
        with self.assertRaisesRegex(ValueError, "硬件中锁定"):
            c.arm(config)
        c.command.assert_not_called()

    def test_imu_diagnostics_signed_units(self):
        c = object.__new__(client.Client); c.imu_test = True
        words = [0x07006869, 2, 123, 0xfffe0001, 0x01024000, 0x0066fffe, 0xfffe]
        c.command = Mock(side_effect=[struct.pack("<III", key, value, 74102) for key, value in zip(range(14, 21), words)])
        result = c.imu_diagnostics()
        self.assertEqual((result["address"], result["who_am_i"], result["fault"]), (0x69, 0x68, 0))
        self.assertTrue(result["ready"] and result["flat_install"] and result["sample_valid"])
        self.assertEqual(result["sample_sequence"], 123)
        self.assertAlmostEqual(result["accel_g"][2], 1)
        self.assertAlmostEqual(result["gyro_dps"][1], -2/16.4)
        self.assertAlmostEqual(result["temperature_c"], -2/340+36.53)
        self.assertEqual([call.args[0] for call in c.command.call_args_list], [0x44]*7)
        c.imu_test = False; c.command.reset_mock()
        with self.assertRaises(ValueError):
            c.imu_diagnostics()
        c.command.assert_not_called()

    def test_release_before_job_never_arms(self):
        c = object.__new__(client.Client)
        c.arm = Mock(side_effect=AssertionError("late ARM"))
        self.assertIsNone(c.drive(Calibration.load(), 100, 0, threading.Event(), threading.Event()))
        c.arm.assert_not_called()

    def test_mpu6500_identity_temperature_and_invalid_data(self):
        c = object.__new__(client.Client); c.imu_test = True
        words = [0x07007068, 60, 123, 0, 0, 0, 0]
        def replies():
            return [struct.pack("<III", key, value, 74102) for key, value in zip(range(14, 21), words)]
        c.command = Mock(side_effect=replies())
        result = c.imu_diagnostics()
        self.assertEqual((result["sensor_model"], result["address_hex"], result["who_am_i_hex"]), ("MPU6500", "0x68", "0x70"))
        self.assertEqual(result["temperature_c"], 21)
        words[0] = 0x00027068
        c.command = Mock(side_effect=replies())
        result = c.imu_diagnostics()
        self.assertFalse(result["sample_valid"])
        self.assertIsNone(result["accel_g"])
        self.assertIsNone(result["gyro_dps"])
        self.assertIsNone(result["temperature_c"])

    def test_tilted_imu_reports_pose_before_calibration_request(self):
        c = object.__new__(client.Client); c.imu_test = True
        c.stop = Mock()
        c.command = Mock(side_effect=AssertionError("tilted IMU must not start calibration"))
        c.imu_diagnostics = Mock(return_value={"ready": True, "sample_valid": True, "fault": 0,
            "flat_install": False, "accel_g": [.778076, -.172363, -.640564]})
        with self.assertRaisesRegex(client.CalibrationRejected, "水平安装条件.*ax=0.778g"):
            c.calibrate(threading.Event())
        c.command.assert_not_called()
        c.stop.assert_called_once()

    def test_imu_calibration_invalid_data_and_valid_flat_pose(self):
        c = object.__new__(client.Client); c.imu_test = True;c.stop = Mock();c.command = Mock()
        c.imu_diagnostics = Mock(return_value={"ready": False, "sample_valid": False, "fault": 3,
            "flat_install": False, "accel_g": None})
        with self.assertRaisesRegex(client.CalibrationRejected, "尚未有效采样"):
            c.calibrate(threading.Event())
        c.command.assert_not_called()
        c.imu_diagnostics.return_value={"ready": True, "sample_valid": True, "fault": 0,
            "flat_install": True, "accel_g": [0, 0, -1]}
        response = bytearray(32);response[0]=1;response[1]=8
        c.command.return_value = bytes(response)
        c.sensors = Mock(return_value={"calibration": 1, "flags": 4})
        self.assertEqual(c.calibrate(threading.Event())["calibration"], 1)
        c.command.assert_called_once_with(0x43, reply=0xc1)

    def test_cancel_before_task_never_arms(self):
        c = object.__new__(client.Client)
        c.arm = Mock(side_effect=AssertionError("late ARM"))
        cancel = threading.Event();cancel.set()
        for kind, value in (("rotate", 90), ("distance", 100)):
            with self.assertRaises(RuntimeError):
                getattr(c, kind)(Calibration.load(), value, 100, cancel)
        c.arm.assert_not_called()

    def test_release_while_arming_sends_stop_without_speed(self):
        d = copy.deepcopy(Calibration.load().data);d["mechanical_track_um"] = 120000
        held = threading.Event();held.set()
        c = object.__new__(client.Client)
        c.arm = Mock(side_effect=lambda _: held.clear())
        c.stop = Mock(return_value="stopped")
        c.wheels = Mock(side_effect=AssertionError("speed after release"))
        self.assertEqual(c.drive(Calibration(d), 100, 0, held, threading.Event()), "stopped")
        c.wheels.assert_not_called()


if __name__ == "__main__":
    unittest.main()
