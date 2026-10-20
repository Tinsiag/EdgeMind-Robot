"""Versioned A741 configuration. Units are explicit and never inferred."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "config/calibration.json"


@dataclass(frozen=True)
class Calibration:
    data: dict

    @classmethod
    def load(cls, path=DEFAULT):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if data.get("schema") != 1:
            raise ValueError("Unsupported calibration schema")
        obj = cls(data)
        obj.values(require_track=False)
        return obj

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def values(self, require_track=True):
        d = self.data
        if len(d["wheel_cpr"]) != 2 or len(d["wheel_diameter_um"]) != 2:
            raise ValueError("轮径和 CPR 必须分别包含左右两项")
        if d.get("schema") != 1 or d.get("imu_axis") != "z" or d.get("lidar_angle_sign") not in (-1, 1):
            raise ValueError("当前支持平放 Z 轴 IMU；请检查 schema、imu_axis 和 lidar_angle_sign")
        track = d["mechanical_track_um"]
        if track is None and require_track:
            raise ValueError("请先实测机械轮距；234 mm 历史转向补偿不能代用")
        # An unmeasured track is represented by no configuration, never a guessed value.
        values = [*d["wheel_cpr"], *d["wheel_diameter_um"], track, d["max_speed_mm_s"],
                  d["revision"], d["imu_yaw_sign"] & 0xffffffff, d["tof_offset_mm"],
                  d["pwm_limit"], d["speed_step_mm_s_per_10ms"], d["pwm_step_per_10ms"]]
        ranges = [(100, 20000)] * 2 + [(10000, 200000)] * 2 + [(50000, 1000000), (40, 400),
                  (1, 0xffffffff), (1, 0xffffffff), (0, 1000), (0, 512), (1, 50), (1, 128)]
        for key, (value, bounds) in enumerate(zip(values, ranges)):
            if key == 4 and value is None:
                continue
            if type(value) is not int or not bounds[0] <= value <= bounds[1]:
                raise ValueError(f"Invalid configuration key {key}")
        if d["imu_yaw_sign"] not in (-1, 1) or d.get("imu_model") != "MPU6050" or d.get("imu_i2c_hz") != 100000:
            raise ValueError("当前固件要求 MPU6050、100 kHz I2C 和 Z 轴安装")
        return values

    def require_hardware(self):
        if self.data.get("hardware_verified") is not True or not self.data.get("imu_model"):
            raise ValueError("传感器针序、上拉电平与 Bank 电压核实后才能启用运动")
        self.values()

    def arc(self, linear_mm_s, angular_deg_s):
        if not all(math.isfinite(x) for x in (linear_mm_s, angular_deg_s)):
            raise ValueError("Non-finite velocity")
        self.values()
        half = math.radians(angular_deg_s) * self.data["mechanical_track_um"] / 2000
        wheels = (linear_mm_s - half, linear_mm_s + half)
        scale = max(1, max(map(abs, wheels)) / self.data["max_speed_mm_s"])
        return tuple(round(v / scale) for v in wheels)

    def distance_mm(self, left_delta, right_delta):
        return tuple(n * math.pi * diameter / (1000 * cpr) for n, diameter, cpr in
                     zip((left_delta, right_delta), self.data["wheel_diameter_um"], self.data["wheel_cpr"]))

    def save(self, path):
        self.values(require_track=False)
        Path(path).write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
