import math,struct,tempfile,threading,time,unittest
from types import SimpleNamespace
from vision_task import Confirmation,associate,encode,VisionTask,CALIBRATION,target_bearing

class VisionTaskTests(unittest.TestCase):
    def box(self,label='bottle',score=.9,x=270):
        return dict(cls=label,score=score,box=[x,100,x+100,350])
    def test_repeated_frame_and_wrong_class_do_not_confirm(self):
        c=Confirmation();b=[self.box()]
        self.assertFalse(c.update(1,b,'bottle')[0])
        for _ in range(10):self.assertFalse(c.update(1,b,'bottle')[0])
        self.assertFalse(c.update(2,b,'bottle')[0]);self.assertTrue(c.update(3,b,'bottle')[0])
        self.assertFalse(c.update(4,[self.box('cup')],'bottle')[0])
    def test_low_score_jump_and_ambiguity_reset(self):
        c=Confirmation()
        for i in range(1,4):c.update(i,[self.box()],'bottle')
        self.assertTrue(c.confirmed)
        self.assertFalse(c.update(4,[self.box(score=.4)],'bottle')[0])
        self.assertFalse(c.update(5,[self.box(),self.box(x=400)],'bottle')[0])
        c.update(6,[self.box()],'bottle');self.assertFalse(c.update(7,[self.box(x=450)],'bottle')[0])
    def test_unverified_calibration_and_wall_rejected(self):
        points=[(a,1000,220,10) for a in range(-10,11)]
        self.assertIsNone(associate(self.box(),points,CALIBRATION,10))
        cal=dict(CALIBRATION,verified=True,target_lidar_observable=True)
        self.assertIsNone(associate(self.box(),points,cal,10))
        target=[(a,1000,220,10) for a in range(-4,5)]
        background=[(a,1400,220,10) for a in list(range(-10,-5))+list(range(6,11))]
        self.assertEqual(associate(self.box(),target+background,cal,10),1000)
        self.assertIsNone(associate(self.box(),target+background,cal,11))
    def test_protocol_offsets(self):
        b=encode(7,123,42,9,1,39,3,220,-100,1000,55,777)
        self.assertEqual(len(b),48);self.assertEqual(b[:4],b'ET10')
        self.assertEqual(struct.unpack_from('<IIII',b,4),(7,123,42,9))
        self.assertEqual(tuple(b[20:24]),(1,39,3,220))
        self.assertEqual(struct.unpack_from('<hHHHHHIQ',b,24),(-100,1000,400,55,60,0,777,0))
    def test_config_never_arms_and_defaults_unverified(self):
        asm=SimpleNamespace(last_frame=0)
        det=SimpleNamespace(lock=threading.Lock(),boxes=[],error='')
        with tempfile.TemporaryDirectory() as p:
            t=VisionTask(['bottle','chair'],asm,det,p)
            self.assertFalse(t.snapshot()['calibrated'])
            t.configure({'label':'chair'});self.assertIsNone(t.session)
            self.assertEqual(t.choose(time.monotonic())[0],0)
            with self.assertRaises(ValueError):t.configure({'label':'red bottle'})
            t.config['calibration']['target_lidar_observable']=True
            t.configure({'label':'bottle'})
            self.assertFalse(t.config['calibration']['target_lidar_observable'])
    def test_measured_bearing_uses_camera_offset_and_yaw(self):
        cal=dict(CALIBRATION,fx=500,cx=300,camera_x_mm=100,camera_y_mm=50,camera_yaw_deg=10)
        x,y=1200,300
        phi=math.atan2(y-50,x-100)-math.radians(10)
        pixel=300-500*math.tan(phi);radial=math.hypot(x-164,y)
        self.assertAlmostEqual(target_bearing(pixel,radial,cal),math.degrees(math.atan2(y,x)),places=6)
    def test_stale_inference_clears_confirmation_and_arrival(self):
        det=SimpleNamespace(lock=threading.Lock(),boxes=[self.box()],error='',source_frame=10,source_time=1)
        with tempfile.TemporaryDirectory() as p:
            t=VisionTask(['bottle'],SimpleNamespace(last_frame=10),det,p)
            t.telemetry=dict(session=123,mode=3,state=15);t.last_rx=10
            t.status=dict(received=10,armed=True,yaw=0,counts=[0,0]);t.session=123
            for i in range(3):t.confirm.update(i,[self.box()],'bottle')
            t.arrival=2
            self.assertEqual(t.choose(10)[0],0)
            self.assertFalse(t.confirm.confirmed);self.assertEqual(t.arrival,0)
    def task_fixture(self,directory):
        det=SimpleNamespace(lock=threading.Lock(),boxes=[self.box()],error='',source_frame=1,source_time=10)
        t=VisionTask(['bottle'],SimpleNamespace(last_frame=10),det,directory)
        t.telemetry=dict(session=123,mode=3,state=15);t.last_rx=10;t.session=123
        t.status=dict(received=10,armed=True,yaw=0,counts=[0,0],ranges=[1500,1500,1500],left_clear=True,right_clear=True)
        return t,det
    def observation(self,t,det,frame):
        det.source_frame=frame;t.last_burst=10;t.pause_until=0
        return t.choose(10)
    def test_confirmed_unmeasured_target_never_advances(self):
        with tempfile.TemporaryDirectory() as p:
            t,det=self.task_fixture(p)
            for i in range(1,5):self.assertEqual(self.observation(t,det,i)[0],0)
            self.assertTrue(t.confirm.confirmed);self.assertIsNone(t.distance)
            det.boxes=[];self.assertEqual(self.observation(t,det,5)[0],0)
    def test_arrival_requires_three_new_measured_observations(self):
        with tempfile.TemporaryDirectory() as p:
            t,det=self.task_fixture(p)
            t.config['calibration']=dict(CALIBRATION,verified=True,target_lidar_observable=True)
            points=[(a,550,220,10) for a in range(-4,5)]
            points += [(a,1200,220,10) for a in list(range(-10,-5))+list(range(6,11))]
            t.points={i:v for i,v in enumerate(points)}
            for i in [1,2,3,3,3,4]:self.assertEqual(self.observation(t,det,i)[0],0)
            action,flags,distance,_=self.observation(t,det,5)
            self.assertEqual((action,flags,distance),(4,3,550))
    def test_approach_and_detour_only_after_reliable_range(self):
        with tempfile.TemporaryDirectory() as p:
            t,det=self.task_fixture(p)
            t.config['calibration']=dict(CALIBRATION,verified=True,target_lidar_observable=True)
            points=[(a,1000,220,10) for a in range(-4,5)]
            points += [(a,1400,220,10) for a in list(range(-10,-5))+list(range(6,11))]
            t.points={i:v for i,v in enumerate(points)}
            for i in [1,2]:self.assertEqual(self.observation(t,det,i)[0],0)
            self.assertEqual(self.observation(t,det,3)[0],1)
            t.status['ranges'][0]=300
            self.assertEqual(self.observation(t,det,4)[0],5)

if __name__=='__main__':unittest.main()
