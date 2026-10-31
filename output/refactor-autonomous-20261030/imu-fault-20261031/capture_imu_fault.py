"""Receive-only IMU fault witness; keeps ages, bus errors and latched causes."""
import argparse
import json
import socket
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'code/camera-car-control/a745-autonomous/host'))
from receiver import decode_status, decode_attitude


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=90)
    ap.add_argument('--output', type=Path, default=Path(__file__).with_name('latest.json'))
    args = ap.parse_args()
    receipt = dict(started_utc=datetime.now(timezone.utc).isoformat(), packets_sent=0,
                   status=[], attitude=[], radar_packets=0, invalid_packets=0)
    previous = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('', 6103))
        sock.settimeout(.2)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            try:
                data, source = sock.recvfrom(2048)
            except socket.timeout:
                continue
            if source != ('192.168.0.2', 6103):
                continue
            try:
                if data[:4] == b'EMS1':
                    value = decode_status(data)
                    sample_time = struct.unpack_from('<I', data, 64)[0]
                    value.update(received_utc=datetime.now(timezone.utc).isoformat(),
                                 imu_time_ms=sample_time, imu_age_ms=(value['ms']-sample_time)&0xffffffff,
                                 imu_errors=struct.unpack_from('<I', data, 76)[0],
                                 imu_seq=struct.unpack_from('<I', data, 100)[0],
                                 imu_fault_sources=data[26], imu_fault_valid_flags=data[27])
                    receipt['status'].append(value)
                    key = value['state'], value['faults'], value['imu_errors'], value['flags'] & 3
                    if key != previous:
                        print(json.dumps({k: value[k] for k in ['ms','revision','state','faults','flags','targets',
                                         'ranges','imu_age_ms','imu_errors','imu_fault_sources']}) ,flush=True)
                        previous = key
                elif data[:4] == b'EMF1':
                    value = decode_attitude(data)
                    value.update(ms=struct.unpack_from('<I', data, 12)[0],
                                 imu_diagnostic=struct.unpack_from('<I', data, 32)[0],
                                 imu_fault_sources=data[42], imu_fault_valid_flags=data[43],
                                 fault_roll=struct.unpack_from('<h', data, 44)[0]*180/32768,
                                 fault_pitch=struct.unpack_from('<h', data, 46)[0]*180/32768)
                    receipt['attitude'].append(value)
                elif data[:4] == b'EML1':
                    receipt['radar_packets'] += 1
            except ValueError:
                receipt['invalid_packets'] += 1
    receipt['ended_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status_packets=len(receipt['status']), attitude_packets=len(receipt['attitude']),
                          last_status=receipt['status'][-1:], last_attitude=receipt['attitude'][-1:],
                          packets_sent=0), indent=2), flush=True)


if __name__ == '__main__':
    main()
