"""MPU6050 diagnostics only. Never sends ARM or wheel commands."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import threading
import time

from calibration import Calibration
from client import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", default="192.168.0.2")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600:
        parser.error("seconds must be in (0, 3600]")
    folder = Path(__file__).resolve().parents[1] / ".local/imu-tests"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".jsonl")
    client = Client(args.ip, timeout=.3)
    try:
        client.connect(Calibration.load())
        if not client.imu_test and not client.motion_lidar:
            raise RuntimeError("需要 IMU-TEST 或 MOTION-LIDAR 固件；不接受旧诊断包")
        if args.calibrate:
            print("请保持模块水平静止；开始零偏校准", flush=True)
            print(json.dumps(client.calibrate(threading.Event()), ensure_ascii=False), flush=True)
        end = time.monotonic()+args.seconds
        with path.open("x", encoding="utf-8") as log:
            while time.monotonic() < end:
                sample = {"host_time": datetime.now().isoformat(),
                          "diagnostics": client.imu_diagnostics(), "sensors": client.sensors()}
                row = json.dumps(sample, ensure_ascii=False)
                log.write(row+"\n");log.flush();print(row, flush=True)
                time.sleep(.3)
    except KeyboardInterrupt:
        print("测试已停止")
    finally:
        client.close()
        print("日志："+str(path), flush=True)


if __name__ == "__main__":
    main()
