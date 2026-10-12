"""Minimal Type-C/CH340E command-line controller for ACG720."""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install pyserial first: python -m pip install pyserial") from exc

from protocol import FrameParser, command_payload, decode_status, frame, GET_STATUS


def ports() -> None:
    for item in list_ports.comports():
        print(f"{item.device}\t{item.description}\t{item.vid!s}:{item.pid!s}")


def open_serial(name: str):
    return serial.Serial(name, 115200, timeout=0.2, write_timeout=0.2)


def send_and_read(port, msg_type: int, payload: bytes, seq: int, wait_s: float = 0.15) -> list[tuple[int, int, bytes]]:
    port.write(frame(msg_type, payload, seq))
    if wait_s <= 0:
        return []
    deadline = time.monotonic() + wait_s
    parser = FrameParser()
    packets = []
    while time.monotonic() < deadline:
        data = port.read(port.in_waiting or 1)
        if data:
            packets.extend(parser.feed(data))
            if packets:
                break
    return packets


def main() -> int:
    parser = argparse.ArgumentParser(description="ACG720 motion controller over CH340E Type-C UART")
    parser.add_argument("--port", help="COM port, e.g. COM7")
    parser.add_argument("--log", type=Path, help="append status samples to CSV")
    parser.add_argument("--duration", type=float, default=1.0, help="seconds for motion commands; default 1.0")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    for name in ("hello", "arm", "stop", "disarm", "status", "clear-fault"):
        sub.add_parser(name)
    p = sub.add_parser("forward"); p.add_argument("speed", type=int)
    p = sub.add_parser("backward"); p.add_argument("speed", type=int)
    p = sub.add_parser("turn"); p.add_argument("linear", type=int); p.add_argument("angular", type=int)
    p = sub.add_parser("rotate"); p.add_argument("angle_deg", type=float); p.add_argument("speed", type=int)
    p = sub.add_parser("set-param"); p.add_argument("param_id", type=int); p.add_argument("value", type=int)
    args = parser.parse_args()
    if args.command == "scan":
        ports(); return 0
    if not args.port:
        parser.error("--port is required for control commands")
    if args.command in {"forward", "backward"}:
        command_args = (args.speed,)
    elif args.command == "turn":
        command_args = (args.linear, args.angular)
    elif args.command == "rotate":
        command_args = (args.angle_deg, args.speed)
    elif args.command == "set-param":
        command_args = (args.param_id, args.value)
    else:
        command_args = ()
    msg_type, payload = command_payload(args.command, *command_args)
    try:
        with open_serial(args.port) as port:
            seq = int(time.time()) & 0xFF
            motion = args.command in {"forward", "backward", "turn", "rotate"}
            deadline = time.monotonic() + args.duration if motion else time.monotonic()
            while True:
                packets = send_and_read(port, msg_type, payload, seq, 0.15 if not motion else 0)
                for response_type, response_seq, response_payload in packets:
                    if response_type == 0x80:
                        status = decode_status(response_payload)
                        print(status)
                        if args.log:
                            new = not args.log.exists()
                            with args.log.open("a", newline="") as f:
                                writer = csv.writer(f)
                                if new: writer.writerow(status.__dataclass_fields__)
                                writer.writerow(status.__dict__.values())
                    else:
                        print(f"response type=0x{response_type:02x} seq={response_seq} payload={response_payload.hex()}")
                if not motion or time.monotonic() >= deadline:
                    break
                seq = (seq + 1) & 0xFF
                time.sleep(0.05)
            if motion:
                port.write(frame(0x04, b"", (seq + 1) & 0xFF))
    except serial.SerialException as exc:
        print(f"serial error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
