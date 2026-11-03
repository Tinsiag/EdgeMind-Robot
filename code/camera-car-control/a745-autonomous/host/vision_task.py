"""Single-class visual search. Local FPGA mode3/S1 is the only ARM source.

Calibration is explicit: unverified intrinsics/extrinsics never enable approach.
Detection display is independent of this module and of task failures.
"""
import json, math, os, socket, struct, threading, time
from pathlib import Path

CALIBRATION = dict(verified=False, fx=520.0, cx=319.5, camera_x_mm=164.0,
                   camera_y_mm=0.0, camera_yaw_deg=0.0, bearing_tolerance_deg=2.0,
                   lidar_height_mm=None, target_lidar_observable=False)
REASONS = {0:'正常',1:'前方受阻',2:'转动空间不足',3:'绕行超出范围',4:'绕行受阻',
           5:'短退恢复',6:'转角异常',7:'状态异常',8:'任务链路失效',9:'搜索超时或超程',
           10:'停稳观察',11:'分段运动结束'}
COLOR_NAMES = ('any', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'black', 'white', 'gray')

def color_from_bgr(image, box):
    """Classify the dominant preset color inside the box's inner 60 percent.

    The result is a filter for a YOLO class, not a replacement for object
    detection. Low-saturation, transparent and mixed-color regions return
    ``unknown`` so a background color cannot arm a task.
    """
    try:
        import cv2, numpy as np
        x1, y1, x2, y2 = map(int, box)
        w, h = x2 - x1, y2 - y1
        if w < 12 or h < 20: return 'unknown', 0.0
        ix, iy = int(w * .2), int(h * .2)
        crop = image[max(0, y1 + iy):min(image.shape[0], y2 - iy),
                     max(0, x1 + ix):min(image.shape[1], x2 - ix)]
        if crop.size == 0: return 'unknown', 0.0
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        sat, val = hsv[..., 1], hsv[..., 2]
        masks = {
            'red': ((hsv[..., 0] < 10) | (hsv[..., 0] >= 170)) & (sat >= 70) & (val >= 45),
            'orange': (hsv[..., 0] >= 10) & (hsv[..., 0] < 22) & (sat >= 70) & (val >= 45),
            'yellow': (hsv[..., 0] >= 22) & (hsv[..., 0] < 38) & (sat >= 70) & (val >= 55),
            'green': (hsv[..., 0] >= 38) & (hsv[..., 0] < 85) & (sat >= 60) & (val >= 40),
            'blue': (hsv[..., 0] >= 85) & (hsv[..., 0] < 140) & (sat >= 60) & (val >= 40),
            'purple': (hsv[..., 0] >= 140) & (hsv[..., 0] < 170) & (sat >= 55) & (val >= 40),
            'black': (val < 55) & (sat < 180),
            'white': (sat < 45) & (val >= 180),
            'gray': (sat < 45) & (val >= 55) & (val < 180),
        }
        ratios = {name: float(mask.mean()) for name, mask in masks.items()}
        color, ratio = max(ratios.items(), key=lambda kv: kv[1])
        if ratio < .22: return 'unknown', ratio
        # Require separation from the second-best color for stable filtering.
        second = sorted(ratios.values(), reverse=True)[1]
        if ratio - second < .04: return 'mixed', ratio
        return color, ratio
    except Exception:
        return 'unknown', 0.0

def encode(seq, session, frame, config, action, label, flags=0, score=0,
           bearing=0, distance=0, age=0, nonce=1):
    return struct.pack('<4sIIII4BhHHHHHIQ', b'ET10', seq & 0xffffffff, session,
                       frame & 0xffffffff, config, action, label, flags, score,
                       bearing, distance, 400, min(1000, int(age)), 60, 0, nonce, 0)

class Confirmation:
    def __init__(self): self.reset()
    def reset(self):
        self.frame=None; self.box=None; self.count=0; self.confirmed=False
    def update(self, frame, boxes, label, threshold=.65, color='any', lock_point=None):
        if frame == self.frame: return self.confirmed, self.box
        self.frame=frame
        candidates=[b for b in boxes if b['cls']==label and b['score']>=threshold and
                    b['box'][2]-b['box'][0]>=12 and b['box'][3]-b['box'][1]>=20 and
                    (color == 'any' or b.get('color') == color)]
        if lock_point is not None and candidates:
            lx, ly = lock_point
            inside=[b for b in candidates if b['box'][0] <= lx <= b['box'][2] and
                    b['box'][1] <= ly <= b['box'][3]]
            if inside: candidates=inside
            else:
                candidates=sorted(candidates, key=lambda b:
                    ((b['box'][0]+b['box'][2])/2-lx)**2+
                    ((b['box'][1]+b['box'][3])/2-ly)**2)[:1]
        if len(candidates)!=1:
            self.box=None;self.count=0;self.confirmed=False;return False,None
        candidate=candidates[0];b=candidate['box']
        if self.box:
            old=self.box['box'];a=(old[2]-old[0])*(old[3]-old[1]);area=(b[2]-b[0])*(b[3]-b[1])
            continuous=abs(b[0]+b[2]-old[0]-old[2])<120 and .5<area/a<2
        else: continuous=False
        self.count=self.count+1 if continuous else 1
        self.box=candidate;self.confirmed=self.count>=3
        return self.confirmed,candidate

def associate(box, points, calibration, now):
    """Find one compact fresh lidar cluster projecting inside the inner box.

    The operator's target plane/height validation is required. No monocular
    box-size distance fallback and no selection of a distant background wall.
    """
    if not calibration.get('verified') or not calibration.get('target_lidar_observable'):
        return None
    x1,_,x2,_=box['box'];lo=x1+(x2-x1)*.15;hi=x2-(x2-x1)*.15
    vals=[];fx=calibration['fx'];cx=calibration['cx'];a=math.radians(calibration['camera_yaw_deg'])
    co,si=math.cos(a),math.sin(a)
    for angle,distance,confidence,stamp in points:
        if now-stamp>.25 or confidence<100 or not 100<distance<4000: continue
        t=math.radians(angle);x=164+distance*math.cos(t)-calibration['camera_x_mm']
        y=distance*math.sin(t)-calibration['camera_y_mm'];forward=x*co+y*si;lateral=-x*si+y*co
        if forward<=0:continue
        pixel=cx-fx*lateral/forward
        if lo<=pixel<=hi:vals.append((distance,angle,pixel))
    if len(vals)<3:return None
    # A spread-out surface / multiple foreground-background depths is ambiguous.
    ds=sorted(v[0] for v in vals);median=ds[len(ds)//2]
    cluster=[v for v in vals if abs(v[0]-median)<=max(60,median*.06)]
    if len(cluster)<3 or len(cluster)<.8*len(vals):return None
    # Both silhouette sides need depth discontinuities. A continuous wall in
    # the same image direction must not supply a small object's range.
    neighbours=[]
    for angle,distance,confidence,stamp in points:
        if now-stamp>.25 or confidence<100:continue
        t=math.radians(angle);x=164+distance*math.cos(t)-calibration['camera_x_mm']
        y=distance*math.sin(t)-calibration['camera_y_mm'];f=x*co+y*si;l=-x*si+y*co
        if f>0:neighbours.append((cx-fx*l/f,distance))
    width=x2-x1
    for low,high in ((x1-width*.35,x1),(x2,x2+width*.35)):
        side=[d for p,d in neighbours if low<=p<=high]
        if not side or min(side)<median+120:return None
    return int(median)

def target_bearing(center, distance, calibration):
    """Body bearing from the calibrated pixel ray and lidar radial distance."""
    phi=math.radians(calibration['camera_yaw_deg'])+math.atan((calibration['cx']-center)/calibration['fx'])
    dx=calibration['camera_x_mm']-164;dy=calibration['camera_y_mm']
    projection=dx*math.cos(phi)+dy*math.sin(phi)
    discriminant=projection*projection+distance*distance-dx*dx-dy*dy
    if discriminant<0:return None
    ray=-projection+math.sqrt(discriminant)
    if ray<=0:return None
    x=calibration['camera_x_mm']+ray*math.cos(phi)
    y=calibration['camera_y_mm']+ray*math.sin(phi)
    return math.degrees(math.atan2(y,x))

class VisionTask:
    def __init__(self, classes, asm, det, directory=None):
        self.classes=classes;self.asm=asm;self.det=det;self.lock=threading.RLock()
        self.path=Path(directory or Path(__file__).parent)/'task-config.json'
        self.config=dict(version=1,label='bottle',threshold=.65,color='any',task_mode='search',
                         lock_point=None,calibration=dict(CALIBRATION))
        if self.path.exists():
            self.config.update(json.loads(self.path.read_text()))
        self.config.setdefault('color', 'any'); self.config.setdefault('task_mode', 'search')
        self.config.setdefault('lock_point', None)
        if self.config['color'] not in COLOR_NAMES: self.config['color']='any'
        if self.config['task_mode'] not in ('off', 'follow', 'search'): self.config['task_mode']='search'
        self.confirm=Confirmation();self.telemetry=None;self.status=None;self.points={}
        self.seq=0;self.session=None;self.nonce=int.from_bytes(os.urandom(4),'little')
        self.message='等待本地模式3 / S1启动';self.error='';self.distance=None;self.action=0
        self.last_rx=0;self.last_burst=0;self.pause_until=0;self.last_frame=None;self.last_confirm_time=0
        self.arrival=0;self.search_started=0;self.search_turns=0;self.search_origin=None;self.search_yaw=0
        self.return_heading=None;self.detour_heading=None;self.detour=False;self.found=False;self.search_node=None
        self.preview=Confirmation();self.preview_distance=None
        self.sock=None
    def configure(self, body):
        if not isinstance(body,dict):raise ValueError('配置必须为JSON对象')
        label=body.get('label', self.config['label'])
        if label not in self.classes:raise ValueError('不支持的YOLO类别')
        color=body.get('color', self.config.get('color', 'any'))
        if color not in COLOR_NAMES:raise ValueError('不支持的颜色')
        task_mode=body.get('task_mode', self.config.get('task_mode', 'search'))
        if task_mode not in ('off','follow','search'):raise ValueError('不支持的任务模式')
        lock_point=body.get('lock_point', self.config.get('lock_point'))
        if lock_point is not None:
            if not isinstance(lock_point,(list,tuple)) or len(lock_point)!=2:
                raise ValueError('lock_point必须是[x,y]')
            lock_point=[max(0,min(639,int(lock_point[0]))),max(0,min(479,int(lock_point[1])))]
        with self.lock:
            if label!=self.config['label'] or color!=self.config.get('color','any'):
                # A camera calibration is reusable. The fact that the previous
                # demonstration object intersects the lidar plane is not.
                self.config['calibration']['target_lidar_observable']=False
            self.config.update(label=label,color=color,task_mode=task_mode,lock_point=lock_point)
            self.config['version']=(self.config['version']+1)&0xffffffff
            self.confirm.reset();self.preview.reset();self.pause_until=time.monotonic()+1;self.arrival=0
            self.path.write_text(json.dumps(self.config,ensure_ascii=False,indent=2)+'\n')
        return self.snapshot()
    def snapshot(self):
        with self.lock:return dict(label=self.config['label'],classes=self.classes,
          color=self.config.get('color','any'),colors=COLOR_NAMES,
          task_mode=self.config.get('task_mode','search'),lock_point=self.config.get('lock_point'),
          config_version=self.config['version'],message=self.message,error=self.error,
          confirmed=self.confirm.confirmed,confirmations=self.confirm.count,distance_mm=self.distance,
          action=self.action,calibrated=bool(self.config['calibration'].get('verified')),
          preview_confirmed=self.preview.confirmed,preview_confirmations=self.preview.count,
          preview_distance_mm=self.preview_distance,
          target_lidar_observable=bool(self.config['calibration'].get('target_lidar_observable')),
          fpga=self.telemetry,status=self.status)
    def ingest(self, data, now):
        with self.lock:
            if len(data)==64 and data[:4]==b'EMT1':
                version,size,revision,ms,session,frame=struct.unpack_from('<HHIIII',data,4)
                if version!=1 or size!=64 or revision!=74513:return
                self.telemetry=dict(revision=revision,ms=ms,session=session,frame=frame,state=data[24],
                                    mode=data[25],reason=data[26],route_stage=data[27],rotation=struct.unpack_from('<i',data,28)[0])
                self.last_rx=now
            elif len(data)==112 and data[:4]==b'EMS1':
                from receiver import decode_status
                self.status=decode_status(data);self.status['received']=now
            elif len(data)==64 and data[:4]==b'EML1':
                raw=data[16:63]
                crc=0
                for b in raw[:-1]:
                    crc^=b
                    for _ in range(8):crc=((crc<<1)^0x4d)&255 if crc&128 else (crc<<1)&255
                if raw[:2]!=b'\x54\x2c' or crc!=raw[-1]:return
                start=struct.unpack_from('<H',raw,4)[0];end=struct.unpack_from('<H',raw,42)[0]
                for i in range(12):
                    d,c=struct.unpack_from('<HB',raw,6+3*i)
                    angle=(270-(start+((end-start)%36000)*i/11)/100)%360
                    self.points[int(angle*2)]=(angle,d,c,now)
    def visual_follow(self, box, score, center, offset, radar_front):
        """Return one bounded visual-follow burst.

        A calibrated camera/lidar range is preferred. When it is unavailable,
        the box area is only a coarse stop-distance proxy; the FPGA still
        applies its front radar, scan freshness and 0.5 s burst limits. The
        proxy is never published as millimetres.
        """
        x1,y1,x2,y2=box
        area=max(1,(x2-x1)*(y2-y1))/(640.0*480.0)
        if radar_front != 65535 and radar_front <= 300:
            self.message='雷达前方过近，停车';return 0,0,0,0
        if abs(offset)>48:
            self.message='视觉目标已确认，低速对准'
            return (2 if offset<0 else 3),0,0,round(offset*100)
        if area>=.20:
            self.message='目标已进入跟随距离，停车保持'
            return 0,0,0,0
        self.message='视觉跟随，低速接近'
        # ET10 flag1 is the FPGA's explicitly bounded visual/search burst. The
        # value 801 is a protocol validity token, not a measured range.
        return 1,1,801,0
    def choose(self, now):
        t=self.telemetry;s=self.status
        if self.config.get('task_mode') == 'off':
            self.message='任务已停止';return 0,0,0,0
        if not t or not s or now-self.last_rx>.4 or now-s['received']>.4 or not s['armed'] or t['mode']!=3 or t['state'] in (0,1,8,14):
            self.message='等待本地模式3 / S1启动';return 0,0,0,0
        if self.config.get('task_mode') == 'follow' and self.config.get('lock_point') is None:
            self.message='跟随模式请在网页点击目标框锁定';return 0,0,0,0
        if self.session!=t['session']:
            self.session=t['session'];self.confirm.reset();self.pause_until=now+.8;self.search_started=now
            self.arrival=0;self.found=False;self.detour=False;self.search_origin=s['yaw'];self.search_yaw=s['yaw'];self.search_turns=0
            self.search_node=s['counts'][0]
        if t['state']==16 or now<self.pause_until:
            self.last_burst=now;self.message='停稳观察';return 0,0,0,0
        with self.det.lock:
            frame=getattr(self.det,'source_frame',0);stamp=getattr(self.det,'source_time',0)
            boxes=list(self.det.boxes);error=self.det.error
        if error or now-stamp>.6 or now-self.asm.last_frame>.6:
            self.confirm.reset();self.arrival=0
            self.message='画面或推理过期，停车';return 0,0,0,0
        if t['state'] not in (6,15,16):
            self.message='FPGA正在执行绕障，等待重新观察';return 5,0,0,0
        if now-self.last_burst>.3:
            self.pause_until=now+.22;self.last_burst=now;return 0,0,0,0
        confirmed,box=self.confirm.update(frame,boxes,self.config['label'],self.config['threshold'],
                                          self.config.get('color','any'),self.config.get('lock_point'))
        new_frame=frame!=self.last_frame;self.last_frame=frame
        if confirmed and box:
            self.found=True;center=(box['box'][0]+box['box'][2])/2;offset=center-319.5
            calibration=self.config['calibration']
            self.distance=associate(box,list(self.points.values()),calibration,now)
            # Pixel-centering does not require inventing a physical angle. A
            # calibrated angle is mandatory in the forward/done packet.
            bearing=round(math.degrees(math.atan((319.5-center)/calibration['fx']))*100)
            physical=target_bearing(center,self.distance,calibration) if self.distance is not None else None
            if physical is not None:bearing=round(physical*100)
            elif self.distance is not None:self.distance=None
            if self.distance is None:self.arrival=0
            if self.distance is None and self.config.get('task_mode') == 'follow':
                return self.visual_follow(box['box'], box['score'], center, offset, s['ranges'][0])
            if (abs(physical)>3 if physical is not None else abs(offset)>24):
                self.message='已确认目标，低速对准';return (2 if bearing>0 else 3),0,0,bearing
            if self.distance is None:
                self.message='已找到目标，距离未确认；请完成相机/雷达标定与目标摆放检查';return 0,0,0,0
            if 450<=self.distance<=600:
                if new_frame:self.arrival+=1
                self.message='确认到达距离' if self.arrival<3 else '已到达，停车'
                return (4 if self.arrival>=3 else 0),3,self.distance,bearing
            self.arrival=0
            if self.distance<450:
                self.message='目标已过近，保持停车';return 0,0,0,0
            if s['ranges'][0]>300:
                self.message='低速接近目标';return 1,3,self.distance,bearing
            self.return_heading=s['yaw'];self.detour=True
            self.message='前方有障碍，交给FPGA绕行';return 5,0,0,0
        elif box:
            self.message='候选目标，连续确认中';return 0,0,0,0
        elif self.found and not self.detour:
            self.message='目标丢失，停车重新观察';return 0,0,0,0
        elif self.config.get('task_mode','search') == 'follow':
            self.message='跟随模式等待目标重新出现';return 0,0,0,0
        if now-self.search_started>115:
            self.message='未找到目标，任务结束';return 0,0,0,0
        # Reactive bounded observation-point search. FPGA independently checks
        # body sweep/translation, and limits whole-task time and wheel travel.
        delta=(s['yaw']-self.search_yaw+180)%360-180
        self.search_turns+=delta;self.search_yaw=s['yaw']
        if abs(self.search_turns)<350:
            self.search_node=s['counts'][0]
            self.message='分步旋转搜寻';return (2 if s['left_clear'] else 3 if s['right_clear'] else 0),0,0,0
        if s['ranges'][0]>800:
            if abs(s['counts'][0]-self.search_node)>=1410:
                self.search_node=s['counts'][0];self.search_turns=0;self.pause_until=now+.4
                return 0,0,0,0
            # Search translation is permitted only with a confirmed geometric
            # observation, so search-only motion uses explicit flag1 below.
            self.message='选择新的安全观察点';return 1,1,min(4000,s['ranges'][0]),0
        self.message='观察点受阻，等待';return 0,0,0,0
    def run(self):
        rx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);rx.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        rx.bind(('',6103));rx.settimeout(.02)
        tx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);tx.bind(('192.168.0.3',6106))
        deadline=0
        while True:
            try:
                try:
                    data,peer=rx.recvfrom(2048)
                    if peer==('192.168.0.2',6103):self.ingest(data,time.monotonic())
                except socket.timeout:pass
                now=time.monotonic()
                if now<deadline:continue
                deadline=now+.1
                with self.lock:
                    with self.det.lock:
                        preview_frame=getattr(self.det,'source_frame',0);preview_time=getattr(self.det,'source_time',0)
                        preview_boxes=list(self.det.boxes)
                    if now-preview_time<.6:
                        ok,b=self.preview.update(preview_frame,preview_boxes,self.config['label'],self.config['threshold'],
                                                  self.config.get('color','any'),self.config.get('lock_point'))
                        self.preview_distance=associate(b,list(self.points.values()),self.config['calibration'],now) if ok else None
                    else:self.preview.reset();self.preview_distance=None
                    action,flags,distance,bearing=self.choose(now);self.action=action;t=self.telemetry
                    if not t or self.session is None:continue
                    with self.det.lock:
                        frame=getattr(self.det,'source_frame',0);stamp=getattr(self.det,'source_time',0)
                    score=round(self.confirm.box['score']*255) if self.confirm.box else 0
                    # Explicit STOP has no age dependency and never creates ARM.
                    packet=encode(self.seq,self.session,frame,self.config['version'],action,
                                  self.classes.index(self.config['label']),flags,score,bearing,distance,
                                  (now-stamp)*1000, self.nonce)
                    tx.sendto(packet,('192.168.0.2',6106));self.seq=(self.seq+1)&0xffffffff;self.error=''
            except Exception as exc:
                with self.lock:self.error=str(exc);self.action=0
                time.sleep(.1)
