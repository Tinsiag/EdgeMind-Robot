"""Read-only UART diagnostic: sends GET_STATUS only, never arms motors."""
from __future__ import annotations
import argparse
import time
import sys
from protocol import GET_STATUS, FrameParser, decode_status, frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    try:
        import serial
        with serial.Serial(args.port, 115200, timeout=0.05, write_timeout=0.5) as port:
            time.sleep(0.2)
            port.reset_input_buffer()
            matched = 0
            for seq in range(1, 4):
                packet = frame(GET_STATUS, seq=seq)
                print(f'TX seq={seq}: {packet.hex(" ")}', flush=True)
                port.write(packet)
                port.flush()
                capture = bytearray()
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    data = port.read(port.in_waiting or 1)
                    if data:
                        capture.extend(data)
                        print(f'RX chunk: {data.hex(" ")}', flush=True)
                print(f'RX total={len(capture)}: {capture.hex(" ") or "<none>"}')
                # Parse the complete capture; preserve evidence even for malformed frames.
                packets = FrameParser().feed(bytes(capture))
                for kind, response_seq, payload in packets:
                    print(f'FRAME type=0x{kind:02x} seq={response_seq} payload={payload.hex(" ")}')
                    if kind == 0x80 and response_seq == seq and len(payload) == 25:
                        print(decode_status(payload))
                        matched += 1
                if not packets:
                    print('NO VALID FRAME: no bytes, incomplete frame, sync or CRC error; inspect RX above.')
            print(f'Matched STATUS replies: {matched}/3. No ARM or motion commands sent.')
            return 0 if matched == 3 else 1
    except (ImportError, OSError, ValueError) as exc:
        print(f'Diagnostic error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
