from dataclasses import replace
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
import threading
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from calibration import Calibration
from telemetry import Snapshot
from mapping import SlamEngine,MappingWorker,signed_delta,map_display_point,map_display_image


def room_ranges(x=0,y=0):
    ranges=[]
    for i in range(361):
        a=math.radians(i-180);dx,dy=math.cos(a),math.sin(a);hits=[]
        if abs(dx)>1e-9:hits.append(((4000 if dx>0 else -2000)-x)/dx)
        if abs(dy)>1e-9:hits.append(((2500 if dy>0 else -3000)-y)/dy)
        ranges.append(round(min(d for d in hits if d>0)))
    return ranges


def snapshot(ms=100,count=0,yaw=0,revision=74104):
    data=bytearray(112)
    struct.pack_into("<4sHHIIIHBBH",data,0,b"EMS1",1,112,1,ms,revision,0x19,0,0,0)
    struct.pack_into("<iiiiii",data,28,0,0,0,0,count,count)
    struct.pack_into("<h",data,52,yaw)
    return Snapshot.parse(data)


class MappingTests(unittest.TestCase):
    def test_persistent_invalid_stream_and_imu_loss_freeze(self):
        worker=object.__new__(MappingWorker)
        worker.frames=1;worker.accepted_host=10;worker.active=True
        worker.lock=threading.Lock();worker.last_id=1
        worker.calibration=Calibration.load();worker.config_hash=worker.calibration.digest
        worker.last=snapshot();worker.engine=Mock()
        with patch("mapping.time.monotonic",return_value=10.2):
            worker.integrate((None,None,(),None,"packet gap"))
        self.assertTrue(worker.active)
        with patch("mapping.time.monotonic",return_value=10.41):
            worker.integrate((None,None,(),None,"packet gap"))
        self.assertFalse(worker.active)
        self.assertIn("400ms",worker.status)
        worker.active=True
        worker.integrate((2,200,((0,1000,100),),replace(snapshot(200),flags=1)))
        self.assertFalse(worker.active)
        self.assertIn("IMU/标定失效",worker.status)
        worker.engine.update.assert_not_called()

    def test_map_image_and_pose_forward_up_left_left(self):
        self.assertEqual(map_display_point((15000,15000,0)),(.5,.5))
        self.assertEqual(map_display_point((18000,15000,0)),(.5,.4))
        self.assertEqual(map_display_point((15000,18000,0)),(.4,.5))
        raw=bytearray([127]*25);raw[2*5+4]=0;raw[4*5+2]=255
        image=map_display_image(bytes(raw),5)
        self.assertEqual(image.getpixel((2,0)),0)
        self.assertEqual(image.getpixel((0,2)),255)

    def test_native_room_occupancy_and_motion(self):
        engine=SlamEngine()
        try:
            for _ in range(8):self.assertTrue(engine.update(room_ranges(),0,0,.1))
            raw,start=engine.state()
            self.assertLess(min(raw),100)
            self.assertGreater(max(raw),200)
            self.assertIn(127,raw)
            for step in range(1,11):self.assertTrue(engine.update(room_ranges(step*10),10.3,0,.1))
            _,end=engine.state()
            self.assertAlmostEqual(end[0]-start[0],100,delta=150)
            self.assertAlmostEqual(end[1]-start[1],0,delta=150)
            self.assertFalse(engine.update([0]*361,0,0,.1))
        finally:engine.close()

    def test_worker_gates_stale_data_and_exports_actual_map(self):
        worker=MappingWorker(Calibration.load())
        try:
            worker.start(Calibration.load())
            deadline=time.monotonic()+3
            while not worker.snapshot()[-1] and time.monotonic()<deadline:time.sleep(.01)
            points=tuple(((180-i)%360*100,d,100) for i,d in enumerate(room_ranges()))
            worker.feed((1,100,points,snapshot(revision=worker.calibration.data["revision"])))
            deadline=time.monotonic()+3
            while worker.snapshot()[3]<1 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(worker.snapshot()[3],1,worker.snapshot()[4])
            worker.feed((1,100,points,snapshot(revision=worker.calibration.data["revision"])))
            time.sleep(.05);self.assertEqual(worker.snapshot()[3],1)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/"room.png"
                worker.save(path)
                for suffix in (".png",".pgm",".yaml",".json"):self.assertTrue(path.with_suffix(suffix).exists())
                record=json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
                self.assertEqual(record["frames"],1)
                self.assertIn("no loop closure",record["engine"])
                self.assertEqual(record["resolution_m"],.05)
                self.assertIn("resolution: 0.050000",path.with_suffix(".yaml").read_text(encoding="utf-8"))
            worker.feed((None,None,(),None,"FPGA包序号缺口"))
            deadline=time.monotonic()+2
            while "短暂中断" not in worker.snapshot()[4] and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(worker.snapshot()[-1])
            self.assertEqual(worker.snapshot()[3],1)
            self.assertIn("FPGA包序号缺口",worker.snapshot()[4])
            update=Mock(wraps=worker.engine.update);worker.engine.update=update
            worker.feed((3,200,points,snapshot(200,2,100,revision=worker.calibration.data["revision"])))
            deadline=time.monotonic()+2
            while worker.snapshot()[3]<2 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(worker.snapshot()[3],2,worker.snapshot()[4])
            self.assertAlmostEqual(update.call_args.args[1],sum(worker.calibration.distance_mm(2,2))/2)
            self.assertAlmostEqual(update.call_args.args[2],100*360/65536*worker.calibration.data["imu_yaw_sign"])
            self.assertEqual(update.call_args.args[3],.1)
            worker.feed((None,None,(),None,"IMU 未校准"))
            deadline=time.monotonic()+2
            while "IMU 未校准" not in worker.snapshot()[4] and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(worker.snapshot()[-1])
            worker.feed((5,1000,points,snapshot(1000,revision=worker.calibration.data["revision"])))
            deadline=time.monotonic()+2
            while worker.snapshot()[-1] and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(worker.snapshot()[3],2)
            self.assertFalse(worker.snapshot()[-1])
            self.assertIn("时间中断",worker.snapshot()[4])
        finally:worker.close()
        self.assertFalse(worker.thread.is_alive())

    def test_counter_and_yaw_wrap(self):
        self.assertEqual(signed_delta(-2147483648,2147483647,32),1)
        self.assertEqual(signed_delta(-32760,32760,16),16)

    def test_lidar_forward_azimuth_matches_core_slam_robot_x_axis(self):
        config=Calibration.load();offset=config.data["lidar_zero_offset_deg"]
        raw_angle=270
        display_up=(-raw_angle+offset)%360
        core_bin=(-raw_angle+offset+180)%360
        core_angle=core_bin-180
        self.assertEqual(display_up,0)
        self.assertEqual(core_angle,0)


if __name__=="__main__":unittest.main()
