"""Bounded, background CoreSLAM occupancy mapping. Never controls the robot."""
import ctypes as ct
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import queue
import threading
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def signed_delta(value, previous, bits):
    return ((value-previous+(1 << (bits-1))) & ((1 << bits)-1))-(1 << (bits-1))


def map_display_point(pose, extent_mm=30000):
    """Native +X forward, +Y left to screen forward-up, left-left."""
    return 1-pose[1]/extent_mm, 1-pose[0]/extent_mm


def map_display_image(raw, pixels=600):
    return Image.frombytes("L",(pixels,pixels),raw).transpose(
        Image.Transpose.FLIP_TOP_BOTTOM).transpose(Image.Transpose.ROTATE_90)


class SlamEngine:
    def __init__(self, pixels=600, meters=30):
        self.pixels, self.meters = pixels, meters
        candidates = (ROOT / ".local/mapping/edgemind_slam.dll",
                      ROOT / ".local/mapping/edgemind_slam.so")
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            raise RuntimeError("建图内核未安装，请运行 scripts/setup_mapping.py")
        self.lib = ct.CDLL(str(path))
        self.lib.em_create.argtypes = [ct.c_int, ct.c_double];self.lib.em_create.restype = ct.c_void_p
        self.lib.em_free.argtypes = [ct.c_void_p]
        self.lib.em_update.argtypes = [ct.c_void_p, ct.POINTER(ct.c_int), ct.c_double, ct.c_double, ct.c_double]
        self.lib.em_update.restype = ct.c_int
        self.lib.em_map.argtypes = [ct.c_void_p, ct.c_void_p]
        self.lib.em_pose.argtypes = [ct.c_void_p, ct.POINTER(ct.c_double)]
        self.handle = self.lib.em_create(pixels, meters)
        if not self.handle:
            raise RuntimeError("无法创建建图内核")

    def update(self, ranges, distance, angle, dt):
        return bool(self.lib.em_update(self.handle, (ct.c_int*361)(*ranges), distance, angle, dt))

    def state(self):
        pixels = ct.create_string_buffer(self.pixels*self.pixels)
        pose = (ct.c_double*3)()
        self.lib.em_map(self.handle, pixels);self.lib.em_pose(self.handle, pose)
        return pixels.raw, tuple(pose)

    def close(self):
        if self.handle:
            self.lib.em_free(self.handle);self.handle = None


class MappingWorker:
    def __init__(self, calibration):
        self.calibration = calibration
        self.jobs = queue.Queue(maxsize=3)
        self.controls = queue.SimpleQueue()
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.image = None;self.pose = None;self.trajectory = [];self.frames = 0
        self.status = "未建图";self.active = False;self.engine = None;self.last = None;self.last_id = None
        self.config_hash = calibration.digest
        self.export_config = copy.deepcopy(calibration.data)
        self.latest = None
        self.pixels, self.meters = 600, 30
        self.accepted_host = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="A741-mapping")
        self.thread.start()

    def command(self, name, value=None):
        if self.closed.is_set():
            return False
        if name != "scan":
            self.controls.put((name, value))
            return True
        try:
            self.jobs.put_nowait((name, value))
            return True
        except queue.Full:
            self.controls.put(("pause", "建图处理积压，地图已冻结；开始新图恢复"))
            return False

    def start(self, calibration):
        return self.command("start", calibration)

    def feed(self, sample):
        return self.command("scan", sample)

    def snapshot(self):
        with self.lock:
            return self.image, self.pose, tuple(self.trajectory), self.frames, self.status, self.active

    def freeze(self, reason):
        with self.lock:
            self.active = False;self.status = reason

    def run(self):
        try:
            while not self.closed.is_set():
                try:
                    name, value = self.controls.get_nowait()
                except queue.Empty:
                    try:
                        name, value = self.jobs.get(timeout=.05)
                    except queue.Empty:
                        if self.active and self.frames and self.accepted_host is not None and time.monotonic()-self.accepted_host>.4:
                            self.freeze("有效完整扫描中断超过400ms，地图已冻结；恢复后新建地图")
                        continue
                try:
                    if name == "start":
                        while True:
                            try:self.jobs.get_nowait()
                            except queue.Empty:break
                        if self.engine:
                            self.engine.close()
                        self.engine = SlamEngine(self.pixels, self.meters)
                        self.calibration = value;self.last=None;self.last_id=None;self.accepted_host=None
                        with self.lock:
                            self.config_hash=value.digest;self.export_config=copy.deepcopy(value.data);self.latest=None
                            self.active=True;self.frames=0;self.image=None;self.pose=None;self.trajectory=[];self.status="等待完整扫描及已校准IMU"
                    elif name == "pause":
                        self.freeze(str(value or "建图已暂停"))
                    elif name == "clear":
                        self.freeze("未建图")
                        with self.lock:
                            self.image=None;self.pose=None;self.trajectory=[];self.frames=0;self.latest=None
                    elif name == "scan" and self.active:
                        self.integrate(value)
                except Exception as exc:
                    self.freeze("建图停止："+str(exc))
        finally:
            if self.engine:
                self.engine.close()

    def integrate(self, sample):
        scan_id, stamp, points, snap = sample[:4]
        if not points or not snap:
            if self.frames and self.accepted_host is not None and time.monotonic()-self.accepted_host>.4:
                self.freeze("有效完整扫描中断超过400ms，地图已冻结；恢复后新建地图")
                return
            reason = sample[4] if len(sample) > 4 else "雷达扫描或配对遥测暂不可用"
            with self.lock:
                self.status = f"扫描短暂中断（{reason}），等待完整扫描；累计地图保留"
            return
        if scan_id == self.last_id:
            return
        if self.last_id is not None and scan_id != ((self.last_id + 1) & 0xffffffff):
            with self.lock:
                self.status = "跳过丢失扫描，用连续里程/航向衔接下一完整圈"
        if abs(signed_delta(snap.ms, stamp, 32)) > 100:
            self.freeze("扫描与遥测时间不匹配，地图已冻结")
            return
        if snap.flags & 0x11 != 0x11 or self.calibration.digest != self.config_hash or snap.revision != self.calibration.data["revision"]:
            if self.frames:
                self.freeze("IMU/标定失效，停止积分；重新校准后开始新图")
            return
        distance=angle=dt=0
        if self.last:
            elapsed=(snap.ms-self.last.ms) & 0xffffffff
            if not 0 < elapsed <= 400:
                self.freeze("遥测时间中断超过400ms，地图已冻结；恢复后新建地图")
                return
            dt=elapsed/1000
            wheels=self.calibration.distance_mm(signed_delta(snap.left_count,self.last.left_count,32),
                                                 signed_delta(snap.right_count,self.last.right_count,32))
            distance=sum(wheels)/2
            angle=signed_delta(snap.yaw_raw,self.last.yaw_raw,16)*360/65536*self.calibration.data["imu_yaw_sign"]
            if abs(distance)>400*dt+15 or abs(angle)>180*dt+5:
                self.freeze("里程/航向跳变，重新校验后需新建地图")
                return
        ranges=[0]*361
        clockwise=self.calibration.data.get("lidar_clockwise",True)
        offset=self.calibration.data.get("lidar_zero_offset_deg",0)
        for raw, distance_mm, confidence in points:
            if confidence<10 or not 60<=distance_mm<=12000:
                continue
            # CoreSLAM bins run -180..+180 counter-clockwise from forward.
            degrees=((-raw/100 if clockwise else raw/100)+offset+180)%360
            index=round(degrees)
            if ranges[index]==0 or distance_mm<ranges[index]:
                ranges[index]=distance_mm
        nonzero=[v for v in ranges if v]
        sectors={index//90 for index,value in enumerate(ranges[:360]) if value}
        if len(nonzero)<30 or len(sectors)<3 or (max(nonzero)-min(nonzero)>5000 and len(nonzero)<90):
            self.freeze("扫描角度覆盖不足或有效回波不足，地图已冻结")
            return
        if not self.engine.update(ranges,distance,angle,dt):
            self.freeze("扫描匹配失败或超出地图边界，停止积分")
            return
        raw,pose=self.engine.state()
        self.last=snap;self.last_id=scan_id;self.accepted_host=time.monotonic()
        with self.lock:
            self.latest={"scan_id":scan_id,"scan_fpga_ms":stamp,"telemetry_seq":snap.seq,"telemetry_fpga_ms":snap.ms}
            self.frames+=1;self.image=raw;self.pose=pose
            self.trajectory.append(pose)
            if len(self.trajectory)>20000:
                self.trajectory=self.trajectory[::2]
            self.status=f"建图 {self.frames} 帧 · {self.engine.meters} m / {self.engine.pixels}px"

    def save(self, destination):
        with self.lock:
            raw,pose,trajectory,frames,status=self.image,self.pose,tuple(self.trajectory),self.frames,self.status
            config=copy.deepcopy(self.export_config);config_hash=self.config_hash;latest=copy.deepcopy(self.latest)
        if raw is None:
            raise ValueError("还没有可保存的地图")
        path=Path(destination)
        path.parent.mkdir(parents=True,exist_ok=True)
        image=map_display_image(raw,self.pixels)
        image.save(path.with_suffix(".png"));image.save(path.with_suffix(".pgm"))
        resolution=self.meters/self.pixels
        origin=-self.meters/2
        path.with_suffix(".yaml").write_text("image: "+path.with_suffix(".pgm").name+f"\nresolution: {resolution:.6f}\norigin: [{origin:.3f}, {origin:.3f}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n",encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({"pose_map_mm":pose,"trajectory_map_mm":trajectory,
            "saved_utc":datetime.now(timezone.utc).isoformat(),"last_input":latest,
            "image_axes":"initial forward up; initial left left; image world X=-native Y, Y=native X",
            "pose_image_mm":None if pose is None else [self.meters*1000-pose[1],pose[0],pose[2]+90],
            "frames":frames,"status":status,"config":config,"config_sha256":config_hash,
            "engine":"CoreSLAM RMHC; local scan matching; no loop closure/navigation",
            "resolution_m":resolution,"size_m":self.meters,"origin_m":[origin,origin],
            "registration":"scan end timestamp matched to nearest EMS1 within100ms; coarse timing; not hardware synchronized"},ensure_ascii=False,indent=2),encoding="utf-8")
        return str(path.with_suffix(".png"))

    def save_reverse_route(self, destination):
        with self.lock:
            route=list(reversed(self.trajectory)); config=copy.deepcopy(self.export_config)
        if len(route)<2:
            raise ValueError("没有足够的轨迹点可导出返程路线")
        path=Path(destination);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"route_map_mm":route,"direction":"reverse",
            "config":config,"note":"反向轨迹导出；当前版本不含定位/自主导航执行器"},ensure_ascii=False,indent=2),encoding="utf-8")
        return str(path)

    def close(self):
        self.closed.set();self.thread.join(timeout=3)
