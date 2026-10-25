"""FPGA map transport and task control. No SLAM or planner runs in this module."""
import base64
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import secrets
import socket
import struct
import time
import zlib

from client import Client, CalibrationRejected
from protocol import crc16_ccitt
from fusion_config import compiled_parameters


@dataclass(frozen=True)
class NavigationStatus:
    state: int
    fault: int
    flags: int
    x_mm: int
    y_mm: int
    yaw_raw: int
    front_mm: int
    map_revision: int
    quality: int
    remaining: int
    expanded: int
    config_crc: int

    @classmethod
    def parse(cls, data):
        if len(data)!=32 or data[0]:
            raise ValueError("FPGA navigation status is invalid")
        return cls(data[1],data[2],data[3],*struct.unpack_from("<iihHI",data,4),data[20],
                   *struct.unpack_from("<HHI",data,22))

    @property
    def geometry_verified(self):
        return bool(self.flags & 0x80)

    @property
    def localized(self):
        return bool(self.flags & 8)


@dataclass(frozen=True)
class MissionStatus:
    active: bool
    cpu_alive: bool
    cpu_fault: bool
    index: int
    count: int
    phase: int
    error: int

    @classmethod
    def parse(cls, data):
        if len(data)!=32 or data[0]:
            raise ValueError("路径点任务回复无效")
        flags=data[1]
        return cls(bool(flags&1),bool(flags&2),bool(flags&4),*data[4:8])


def waypoint_payload(point):
    if len(point)!=3 or not all(math.isfinite(v) for v in point):
        raise ValueError("路径点需要有效的X、Y和朝向")
    x,y,degrees=point
    if not (-3100<=x<=3100 and -3100<=y<=3100):
        raise ValueError("路径点超出地图内部范围")
    return struct.pack("<BBH",int((x+3200)//50),int((y+3200)//50),round(degrees*65536/360)&65535)


class MapTransport:
    def __init__(self, ip):
        self.peer=(ip,6104)
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0",6104))
        self.socket.settimeout(.5)
        self.number=secrets.randbelow(0x7fffffff)

    def close(self):
        self.socket.close()

    def command(self, kind, payload=b""):
        if kind not in (0x50,0x51,0x52) or len(payload)>28:
            raise ValueError("Map channel accepts stopped map operations only")
        self.number=(self.number+1)&0xffffffff
        body=struct.pack("<4sIBB",b"EMM1",self.number,kind,len(payload))+payload
        self.socket.sendto(body+struct.pack("<H",crc16_ccitt(body)),self.peer)
        deadline=time.monotonic()+.5
        while time.monotonic()<deadline:
            try:
                data,source=self.socket.recvfrom(128)
            except socket.timeout as exc:
                raise TimeoutError(f"地图UDP请求{self.number}超时；操作未确认") from exc
            if source!=self.peer or len(data)!=44:
                continue
            if struct.unpack_from("<4sIBB",data)!=(b"EMM1",self.number,0xd0,32):
                continue
            if crc16_ccitt(data[:-2])!=struct.unpack_from("<H",data,42)[0]:
                continue
            return data[10:42]
        raise TimeoutError("地图回复不匹配")


def map_record(raw, calibration, geometry, status=None):
    if len(raw)!=4096:
        raise ValueError("FPGA地图必须包含4096字节")
    return {"format":"A741-grid-v1","width":128,"height":128,"resolution_mm":50,"origin_mm":[-3200,-3200],
            "cells":"2 bits/cell, row-major, x-low, little bit order: unknown=0 free=1 occupied=2 reserved=3",
            "data_base64":base64.b64encode(raw).decode("ascii"),"crc32":zlib.crc32(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),"configuration":calibration.data,"configuration_sha256":calibration.digest,
            "geometry":geometry,"status":vars(status) if status else None,"host_unix":time.time()}


def load_map(path):
    record=json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("format")!="A741-grid-v1" or (record.get("width"),record.get("height"),record.get("resolution_mm"))!=(128,128,50):
        raise ValueError("需要128×128、50mm/格的A741地图，不能将旧CoreSLAM地图直接上传")
    raw=base64.b64decode(record["data_base64"],validate=True)
    if len(raw)!=4096 or zlib.crc32(raw)!=record["crc32"] or hashlib.sha256(raw).hexdigest()!=record["sha256"]:
        raise ValueError("地图长度、CRC32或SHA256不匹配")
    return raw


class FusionClient(Client):
    def connect(self, calibration):
        status=super().connect(calibration)
        capability=self.command_idempotent(0x40,reply=0xc0)
        self.fusion_enabled=bool(struct.unpack_from("<H",capability,4)[0]&0x800)
        self.map_transport=None
        if self.fusion_enabled:
            geometry=json.loads((Path(__file__).resolve().parents[1]/"config/geometry.json").read_text(encoding="utf-8"))
            self.compiled_geometry=geometry
            _,self.expected_config_crc=compiled_parameters(geometry,calibration.data)
            actual=self.navigation_status().config_crc
            if actual!=self.expected_config_crc:
                raise CalibrationRejected(f"FPGA几何配置不匹配：位流{actual:08x}，上位机{self.expected_config_crc:08x}；禁止运动")
        return status

    def close(self):
        mapping=getattr(self,"map_transport",None)
        if mapping:
            mapping.close();self.map_transport=None
        super().close()

    def fusion_command(self, kind, payload=b"", map_channel=False):
        if not getattr(self,"fusion_enabled",False):
            raise CalibrationRejected("当前固件未启用FPGA融合接口；请使用匹配的新构建")
        if map_channel:
            if self.map_transport is None:
                self.map_transport=MapTransport(self.peer[0])
            result=self.map_transport.command(kind,payload)
        else:
            result=self.command(kind,payload,reply=0xd0)
        if len(result)!=32:
            raise CalibrationRejected("FPGA融合回复长度错误")
        if result[0]:
            reason={1:"几何/定位/雷达条件未满足，导航被锁定",2:"当前正在运动或地图/定位繁忙",3:"位置超出地图",4:"整图CRC32错误"}.get(result[0],"FPGA拒绝操作")
            raise CalibrationRejected(reason)
        return result

    def navigation_status(self):
        return NavigationStatus.parse(self.fusion_command(0x57))

    def mission_command(self, operation, payload=b""):
        if operation not in range(5) or len(payload)!=(4 if operation==1 else 0):
            raise ValueError("路径点任务操作或载荷错误")
        return MissionStatus.parse(self.fusion_command(0x58,bytes([operation])+payload))

    def run_waypoints(self, calibration, points, cancel, callback):
        if not 1<=len(points)<=16:
            raise ValueError("请选择1～16个路径点")
        encoded=[waypoint_payload(p) for p in points]
        status=self.navigation_status()
        if not status.geometry_verified or not status.localized:
            raise CalibrationRejected("请先设置起点并等待有效雷达定位")
        if status.flags&0x40:
            raise CalibrationRejected("请等待当前路径预览完成")
        try:
            self.disarm()
            self.mission_command(0)
            for point in encoded:
                if cancel.is_set():raise CalibrationRejected("任务已取消，未启动")
                self.mission_command(1,point)
            self.arm(calibration)
            if cancel.is_set():raise CalibrationRejected("任务已取消，未启动")
            result=self.mission_command(2)
            # After explicit start, the onboard CPU supplies the control lease.
            # Polling displays progress only; navigation does not run in Python.
            seen_active=False
            deadline=time.monotonic()+len(points)*125+5
            while time.monotonic()<deadline and not cancel.is_set():
                result=self.mission_command(4);callback(result)
                if result.cpu_fault or result.error:
                    raise CalibrationRejected(f"路径点任务停止：原因{result.error}，软核故障={result.cpu_fault}")
                if result.active:seen_active=True
                elif seen_active and result.index==len(points):return result
                elif not result.active and result.phase==0 and result.index==len(points):return result
                elif not result.cpu_alive:raise CalibrationRejected("软核心跳无效，任务已停止")
                time.sleep(.05)
            raise CalibrationRejected("路径点任务取消或超时")
        finally:
            self.stop()

    def prepare_lidar(self, calibration, cancel=None):
        self.lidar(calibration.data.get("lidar_duty_permille",400))
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if cancel is not None and cancel.is_set():
                raise CalibrationRejected("雷达等待已取消")
            self.heartbeat()
            if self.navigation_status().flags & 2:
                return
            time.sleep(.05)
        raise CalibrationRejected("没有获得完整有效LD06扫描；不会启动车轮")

    def arm(self, calibration):
        if getattr(self,"fusion_enabled",False):
            _,expected=compiled_parameters(self.compiled_geometry,calibration.data)
            if self.navigation_status().config_crc!=expected:
                raise CalibrationRejected("FPGA与当前雷达/几何配置不匹配；须重新构建匹配固件")
            self.prepare_lidar(calibration)
        return super().arm(calibration)

    def map_begin(self, build=False):
        self.disarm()
        self.fusion_command(0x50,bytes([bool(build)]),map_channel=True)
        time.sleep(.02)

    def map_commit(self, crc=0):
        self.disarm()
        return struct.unpack_from("<I",self.fusion_command(0x52,struct.pack("<I",crc),map_channel=True),4)[0]

    def download_map(self, cancel):
        self.disarm();result=bytearray()
        for address in range(0,4096,24):
            if cancel.is_set():
                raise CalibrationRejected("地图下载已取消")
            size=min(24,4096-address)
            packet=self.fusion_command(0x51,struct.pack("<BHB",0,address,size),map_channel=True)
            result.extend(packet[4:4+size]);self.heartbeat()
        return bytes(result)

    def upload_map(self, raw, cancel):
        if len(raw)!=4096:
            raise ValueError("地图长度错误")
        self.map_begin()
        for address in range(0,4096,24):
            if cancel.is_set():
                raise CalibrationRejected("地图上传已取消，地图未提交")
            data=raw[address:address+24]
            self.fusion_command(0x51,struct.pack("<BHB",1,address,len(data))+data,map_channel=True)
            self.heartbeat()
        actual=self.map_commit(zlib.crc32(raw))
        if actual!=zlib.crc32(raw):
            raise CalibrationRejected("FPGA地图CRC回读不一致")

    def set_initial_pose(self, x, y, degrees):
        self.disarm()
        heading=round(degrees*65536/360)&65535
        self.fusion_command(0x53,struct.pack("<iiH",round(x),round(y),heading))

    def goal(self, x, y, degrees):
        if not all(math.isfinite(v) for v in (x,y,degrees)) or not (-3200<=x<3200 and -3200<=y<3200):
            raise ValueError("目标必须在6.4m地图内")
        self.disarm()
        self.fusion_command(0x54,struct.pack("<BBH",int((x+3200)//50),int((y+3200)//50),round(degrees*65536/360)&65535))

    def navigate(self, calibration, cancel, alive, callback):
        status=self.navigation_status()
        if not status.geometry_verified or not status.localized:
            raise CalibrationRejected("请先核实几何参数、标注初始位姿并等待雷达定位")
        self.prepare_lidar(calibration,cancel)
        try:
            # Route preview can take seconds. Keep disarmed until preview and localization finish.
            preview_deadline=time.monotonic()+30
            while status.flags&0x40 or not status.localized:
                if cancel.is_set() or not alive() or time.monotonic()>=preview_deadline:
                    raise CalibrationRejected("规划/定位等待取消或超时；未启动导航")
                self.heartbeat();status=self.navigation_status();callback(status);time.sleep(.03)
            self.arm(calibration)
            self.fusion_command(0x55)
            deadline=time.monotonic()+180
            seen_active=False
            while not cancel.is_set() and time.monotonic()<deadline:
                if not alive():
                    raise CalibrationRejected("界面租期过期，导航已取消")
                self.heartbeat();status=self.navigation_status();callback(status)
                motion=self.status()
                if motion.faults or status.fault:
                    raise CalibrationRejected(f"导航停车：FPGA faults=0x{motion.faults:04x}，导航原因={status.fault}")
                if status.state==4:
                    deadline=max(deadline,time.monotonic()+5)
                seen_active=seen_active or bool(status.flags&1)
                if seen_active and not status.flags&1 and not status.flags&0x40:
                    return status
                time.sleep(.03)
            raise CalibrationRejected("导航取消或超时；须人工重新启动")
        finally:
            self.stop()
