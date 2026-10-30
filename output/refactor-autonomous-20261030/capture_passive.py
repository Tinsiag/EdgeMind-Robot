"""Receive the real board's broadcasts without transmitting any packet."""
import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'code/camera-car-control/a745-autonomous/host'))
from receiver import decode_status, decode_attitude

ap = argparse.ArgumentParser()
ap.add_argument('--seconds', type=int, default=20)
ap.add_argument('--output', type=Path, default=Path(__file__).with_name('HARDWARE-TELEMETRY.json'))
args = ap.parse_args()
receipt = {'started_utc': datetime.now(timezone.utc).isoformat(), 'packets_sent': 0,
           'source': '192.168.0.2:6103', 'status': [], 'attitude': [], 'radar_packets': 0, 'invalid_packets': 0}
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
                receipt['status'].append(decode_status(data))
            elif data[:4] == b'EMF1':
                receipt['attitude'].append(decode_attitude(data))
            elif data[:4] == b'EML1':
                receipt['radar_packets'] += 1
        except ValueError:
            receipt['invalid_packets'] += 1
receipt['ended_utc'] = datetime.now(timezone.utc).isoformat()
args.output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status_packets': len(receipt['status']), 'latest_status': receipt['status'][-1:] or None,
                  'latest_attitude': receipt['attitude'][-1:] or None,
                  'attitude_packets': len(receipt['attitude']), 'radar_packets': receipt['radar_packets'],
                  'invalid': receipt['invalid_packets'], 'packets_sent': 0}, indent=2))
