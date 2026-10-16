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

from protocol import FrameParser, command_payload, decode_status, frame, GET_STATUS, STOP, HEARTBEAT, ROTATE


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


def run_motion(port, msg_type: int, payload: bytes, seq: int, duration: float, log=None) -> None:
    """Bounded motion with best-effort STOP while the serial port is still open.

    ROTATE is submitted once. Heartbeat only renews TTL; it never restarts rotation.
    A disconnected link cannot guarantee STOP delivery: FPGA TTL is the fallback.
    """
    deadline = time.monotonic() + duration
    started = time.monotonic()
    original_timeout = port.timeout
    try:
        port.timeout = 0.01
        port.write(frame(msg_type, payload, seq))
        while time.monotonic() < deadline:
            time.sleep(0.05)
            seq = (seq + 1) & 0xFF
            port.write(frame(HEARTBEAT if msg_type == ROTATE else msg_type,
                             b"" if msg_type == ROTATE else payload, seq))
            seq = (seq + 1) & 0xFF
            packets = send_and_read(port, GET_STATUS, b"", seq, 0.03)
            if not any(kind == 0x80 and response_seq == seq for kind, response_seq, _ in packets):
                raise RuntimeError("No matching STATUS during motion; stopping")
            for kind, response_seq, response_payload in packets:
                if kind != 0x80 or response_seq != seq:
                    continue
                status = decode_status(response_payload)
                print(status)
                if log:
                    new = not log.exists()
                    with log.open("a", newline="") as f:
                        writer = csv.writer(f)
                        if new: writer.writerow(status.__dataclass_fields__)
                        writer.writerow(status.__dict__.values())
                if status.faults or status.state == 0:
                    raise RuntimeError("Motion rejected/disarmed or FPGA fault; stopping")
                if msg_type == ROTATE and status.state == 1 and time.monotonic()-started > 0.1:
                    return
    finally:
        try:
            port.write(frame(STOP, b"", (seq + 1) & 0xFF))
            port.flush()
        except (serial.SerialException, OSError) as exc:
            print(f"STOP delivery failed: {exc}; do not assume the motor stopped. "
                  "FPGA TTL and physical power isolation are the fallback.", file=sys.stderr)
        finally:
            port.timeout = original_timeout


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
            if motion:
                if args.duration <= 0:
                    parser.error("--duration must be positive")
                run_motion(port, msg_type, payload, seq, args.duration, args.log)
            else:
                packets = send_and_read(port, msg_type, payload, seq)
                matched = [(kind, data) for kind, response_seq, data in packets
                           if response_seq == seq]
                if not matched:
                    print("No matching valid reply received. Run serial_diagnose.py to inspect raw bytes.", file=sys.stderr)
                    return 1
                for kind, data in matched:
                    if kind == 0x80:
                        status = decode_status(data)
                        print(status)
                        if args.log:
                            new = not args.log.exists()
                            with args.log.open("a", newline="") as f:
                                writer = csv.writer(f)
                                if new: writer.writerow(status.__dataclass_fields__)
                                writer.writerow(status.__dict__.values())
                    else:
                        print(f"response type=0x{kind:02x} payload={data.hex()}")
    except KeyboardInterrupt:
        print("Interrupted; best-effort STOP attempted for motion.", file=sys.stderr)
        return 130
    except (serial.SerialException, RuntimeError, ValueError) as exc:
        print(f"serial error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
