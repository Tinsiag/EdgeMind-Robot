"""Basic on-board avoidance control; the PC sends settings and observes only."""
from dataclasses import dataclass
import json
from pathlib import Path
import struct
from client import Client, CalibrationRejected
from board_config import compiled_parameters


@dataclass(frozen=True)
class AvoidanceStatus:
    state: int
    fault: int
    flags: int
    yaw_raw: int
    front_mm: int
    left_mm: int
    right_mm: int
    cpu_flags: int
    uptime_ms: int
    config_crc: int
    roll_raw: int = 0
    pitch_raw: int = 0

    @property
    def active(self):
        return bool(self.flags & 1)

    @classmethod
    def parse(cls, data):
        if len(data)!=32 or data[0] or data[30:32]!=b"\x01\x01":
            raise CalibrationRejected("固件不是当前基础避障版本")
        return cls(data[1],data[2],data[3],*struct.unpack_from("<hHHH",data,12),
                   data[20],*struct.unpack_from("<II",data,22),*struct.unpack_from("<hh",data,4))


class AvoidanceClient(Client):
    def connect(self, calibration):
        status=super().connect(calibration)
        capability=self.command_idempotent(0x40,reply=0xc0)
        self.avoidance_enabled=bool(struct.unpack_from("<H",capability,4)[0]&0x800)
        if self.avoidance_enabled:
            geometry=json.loads((Path(__file__).resolve().parents[1]/"config/geometry.json").read_text(encoding="utf-8"))
            _,expected=compiled_parameters(geometry,calibration.data)
            if self.avoidance_status().config_crc!=expected:
                raise CalibrationRejected("FPGA与上位机的车体配置不匹配，禁止运动")
        return status

    def avoidance_command(self, kind, payload=b""):
        if not getattr(self,"avoidance_enabled",False):
            raise CalibrationRejected("当前固件没有基础避障接口")
        data=self.command(kind,payload,reply=0xd0)
        if len(data)!=32 or data[0]:
            raise CalibrationRejected("操作被拒绝，请检查ARM、CPU、配置及控制权状态")
        return data

    def avoidance_status(self):
        return AvoidanceStatus.parse(self.avoidance_command(0x57))

    def start_avoidance(self):
        if getattr(self,"sensors_only",False):
            raise CalibrationRejected("传感器调试模式禁止启动避障")
        return self.avoidance_command(0x59,b"\x01")

    def stop_avoidance(self):
        return self.avoidance_command(0x59,b"\x00")
