"""Passive FPGA telemetry capture. Sends no commands and never arms motors."""
import argparse
from collections import Counter, deque
from dataclasses import asdict
import json
from pathlib import Path
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from telemetry import ScanAssembler, Snapshot, lidar_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/lidar-debug")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024*1024)
    sock.bind(("", 6103));sock.settimeout(.2)
    scan = ScanAssembler();counts = Counter();reasons = Counter();examples = []
    stamps = deque(maxlen=100);first = last = None
    previous = None;previous_angle = None;previous_step = 0
    started = time.monotonic()
    with (args.output / "packets.bin").open("wb") as raw_log, (args.output / "events.jsonl").open("w", encoding="utf-8") as log:
        while time.monotonic() - started < args.seconds:
            try:data, source = sock.recvfrom(2048)
            except socket.timeout:continue
            if source != ("192.168.0.2", 6103):continue
            now = time.monotonic()
            raw_log.write(struct.pack("<dH", now - started, len(data)) + data)
            if data[:4] == b"EMS1":
                snap = Snapshot.parse(data);stamps.append(snap)
                if first is None:first = asdict(snap)
                last = asdict(snap);counts["snapshots"] += 1
                continue
            counts["lidar_packets"] += 1
            try:points = lidar_points(data[16:63])
            except ValueError:
                counts["bad_packets"] += 1;continue
            counts["internal_header_candidates"] += sum(data[16+i:18+i] == b"\x54\x2c" for i in range(1, 46))
            if previous_angle is not None:
                first_gap=(points[0][0]-previous_angle)%36000
                if first_gap > max(100,previous_step*3):
                    counts["angle_gaps"] += 1
                    reasons["angle_gap_cdeg"] += first_gap
                    if len(examples)<8:examples.append({"kind":"angle_gap","gap_cdeg":first_gap,"packet_seq":struct.unpack_from("<I",data,8)[0]})
                elif first_gap < max(1,previous_step//2):
                    counts["angle_overlaps"] += 1
                    if len(examples)<8:examples.append({"kind":"angle_overlap","gap_cdeg":first_gap,"packet_seq":struct.unpack_from("<I",data,8)[0]})
            previous_angle = points[-1][0]
            previous_step=(points[-1][0]-points[0][0])%36000/11
            delta = None
            if previous:
                delta = {"packet_seq": (struct.unpack_from("<I",data,8)[0]-previous["seq"])&0xffffffff,
                         "fpga_ms":(struct.unpack_from("<I",data,12)[0]-previous["stamp"])&0xffffffff,
                         "host_ms":(now-previous["host"])*1000}
                if delta["packet_seq"]!=1:counts["eml1_sequence_gaps"]+=1
                if delta["fpga_ms"]>100:counts["eml1_timestamp_gaps_over_100ms"]+=1
                if delta["host_ms"]>100:counts["host_arrival_gaps_over_100ms"]+=1
            previous={"seq":struct.unpack_from("<I",data,8)[0],"stamp":struct.unpack_from("<I",data,12)[0],"host":now}
            broken = scan.discontinuities;completed = scan.completed_id
            scan.feed(data, now)
            if scan.discontinuities != broken:
                reasons["scan_discontinuity"] += 1
                log.write(json.dumps({"host_s":now-started,"seq":scan.last_seq,"stamp":scan.last_time,
                    "gaps":scan.gaps,"reason":scan.last_discontinuity,"delta":delta})+"\n")
            if scan.completed_id != completed:
                counts["complete_scans"] += 1
                if stamps:
                    diff = min(abs(((s.ms-scan.completed_stamp+0x80000000)&0xffffffff)-0x80000000) for s in stamps)
                    if diff > 100:counts["scan_pairing_over_100ms"] += 1
    sock.close()
    report = {"seconds":time.monotonic()-started,"counts":dict(counts),"reasons":dict(reasons),
              "scan_errors":scan.errors,"scan_gaps":scan.gaps,"first_snapshot":first,"last_snapshot":last,"examples":examples,
              "no_control_commands_sent":True,"capture_payload":str(args.output/"packets.bin")}
    (args.output / "summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":main()
