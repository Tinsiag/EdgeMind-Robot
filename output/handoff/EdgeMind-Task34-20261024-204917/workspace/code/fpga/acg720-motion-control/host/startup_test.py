"""A721 single-wheel bench test. Running this script requests physical motion.

Use only after reading release/A721-20261017/README.md, with wheels raised.
"""
import argparse
import struct
import sys

from serial_control import open_serial, send_and_read, run_motion
from protocol import STOP, GET_STATUS, ARM, SET_PARAM, SET_WHEEL_SPEED, decode_status


def test_wheel(port, wheel):
    seq = 0

    def request(kind, payload=b""):
        nonlocal seq
        seq = (seq + 1) & 0xFF
        packets = send_and_read(port, kind, payload, seq)
        matches = [p for p in packets if p[0] == 0x80 and p[1] == seq]
        if not matches:
            raise RuntimeError("No matching STATUS; test aborted")
        return decode_status(matches[-1][2])

    try:
        request(STOP)
        status = request(GET_STATUS)
        if status.state != 0 or status.faults or status.left_pwm or status.right_pwm:
            raise RuntimeError(f"Preflight requires DISARMED/no faults/zero PWM: {status}")
        # Zero output before parameters; do not clear faults automatically.
        for param_id, value in [(9, 0), (0, 1469), (1, 1471), (2, 66), (3, 66),
                                (4, 121), (5, 400), (6, 491), (10, 50)]:
            request(SET_PARAM, struct.pack('<BI', param_id, value))
        request(ARM)
        status = request(GET_STATUS)
        print('ARM check:', status)
        if status.state != 1 or status.faults or status.left_pwm or status.right_pwm:
            raise RuntimeError("ARM was not confirmed; no motion sent")
        request(SET_PARAM, struct.pack('<BI', 9, 512))
        values = (400, 0) if wheel == 'left' else (0, 400)
        print(f'{wheel}: target 400 mm/s, PWM cap 512/1024, duration 1 s')
        # Existing runner polls every ~50 ms, renews TTL=250 ms, and sends STOP
        # on normal completion, Ctrl+C, missing telemetry or a reported fault.
        run_motion(port, SET_WHEEL_SPEED, struct.pack('<ii', *values), (seq + 1) & 0xFF, 1.0)
    finally:
        # Try both actions independently, even if one request fails.
        errors = []
        for kind, payload in [(STOP, b''), (SET_PARAM, struct.pack('<BI', 9, 0))]:
            try:
                request(kind, payload)
            except Exception as exc:
                errors.append(str(exc))
        try:
            status = request(GET_STATUS)
            print('Final:', status)
            if status.state not in (0, 3) or status.left_pwm or status.right_pwm:
                errors.append('Stopped output was not confirmed')
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise RuntimeError('Cleanup incomplete; disconnect VM: ' + '; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--wheel', choices=('left', 'right'), required=True)
    args = parser.parse_args()
    try:
        with open_serial(args.port) as port:
            test_wheel(port, args.wheel)
        return 0
    except KeyboardInterrupt:
        print('Interrupted; disconnect VM and check final status.', file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Test stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
