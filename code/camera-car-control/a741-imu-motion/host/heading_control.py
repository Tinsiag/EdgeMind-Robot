"""Bounded host heading outer loop; wheel PI remains on the FPGA."""
import math


class HeadingPD:
    def __init__(self, calibration, sensor):
        d = calibration.data
        self.sign = d["imu_yaw_sign"]
        self.origin = sensor["yaw"]
        self.stamp = sensor["ms"]
        self.rate = 0.0
        self.correction = 0.0
        self.kp = d.get("heading_kp_mm_s_per_deg", 1.0)
        self.kd = d.get("heading_kd_mm_s_per_deg_s", 0.5)
        self.limit = d.get("heading_correction_limit_mm_s", 15.0)
        self.slew = d.get("heading_correction_slew_mm_s2", 40.0)
        self.bias = sensor["gyro"]

    def wheels(self, speed, sensor, maximum):
        elapsed = (sensor["ms"]-self.stamp) & 0xffffffff
        if elapsed > 150:
            raise ValueError("IMU heading sample gap exceeds 150ms")
        error = ((sensor["yaw"]-self.origin+32768) % 65536-32768)*360/65536*self.sign
        if elapsed:
            dt = elapsed/1000
            rate = (sensor["gyro"]-self.bias)/16.4*self.sign
            alpha = dt/(0.08+dt)
            self.rate += alpha*(rate-self.rate)
            limit = min(self.limit, abs(speed)*0.2, maximum-abs(speed))
            desired = max(-limit, min(limit, self.kp*error+self.kd*self.rate))
            step = self.slew*dt
            self.correction += max(-step, min(step, desired-self.correction))
            self.stamp = sensor["ms"]
        # Do not reverse a slow wheel or exceed the configured wheel limit.
        cap = min(self.limit, abs(speed)*0.2, max(0, maximum-abs(speed)))
        correction = max(-cap, min(cap, self.correction))
        return round(speed+correction), round(speed-correction)
