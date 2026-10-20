from dataclasses import replace
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"host"))
from calibration import Calibration
from telemetry import Snapshot
from mapping import SlamEngine,MappingWorker,signed_delta


def room_ranges(x=0,y=0):
    ranges=[]
    for i in range(361):
        a=math.radians(i-180);dx,dy=math.cos(a),math.sin(a);hits=[]
        if abs(dx)>1e-9:hits.append(((4000 if dx>0 else -2000)-x)/dx)
        if abs(dy)>1e-9:hits.append(((2500 if dy>0 else -3000)-y)/dy)
        ranges.append(round(min(d for d in hits if d>0)))
    return ranges


def snapshot(ms=100,count=0,yaw=0):
    data=bytearray(112)
    struct.pack_into("<4sHHIIIHBBH",data,0,b"EMS1",1,112,1,ms,74103,0x19,0,0,0)
    struct.pack_into("<iiiiii",data,28,0,0,0,0,count,count)
    struct.pack_into("<h",data,52,yaw)
    return Snapshot.parse(data)


class MappingTests(unittest.TestCase):
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
            worker.feed((1,100,points,snapshot()))
            deadline=time.monotonic()+3
            while worker.snapshot()[3]<1 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(worker.snapshot()[3],1,worker.snapshot()[4])
            worker.feed((1,100,points,snapshot()))
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
            worker.feed((2,200,points,snapshot(200)))
            deadline=time.monotonic()+2
            while worker.snapshot()[3]<2 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(worker.snapshot()[3],2,worker.snapshot()[4])
            worker.feed((4,300,points,snapshot(300)))
            deadline=time.monotonic()+2
            while worker.snapshot()[-1] and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(worker.snapshot()[-1])
            self.assertIn("扫描丢失",worker.snapshot()[4])
            worker.feed((5,1000,points,snapshot(1000)))
            deadline=time.monotonic()+2
            while worker.snapshot()[-1] and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(worker.snapshot()[-1]);self.assertEqual(worker.snapshot()[3],2)
        finally:worker.close()
        self.assertFalse(worker.thread.is_alive())

    def test_counter_and_yaw_wrap(self):
        self.assertEqual(signed_delta(-2147483648,2147483647,32),1)
        self.assertEqual(signed_delta(-32760,32760,16),16)


if __name__=="__main__":unittest.main()
