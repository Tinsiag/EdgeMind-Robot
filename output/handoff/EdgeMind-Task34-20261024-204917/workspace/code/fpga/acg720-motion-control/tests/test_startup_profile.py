"""Single-wheel bench configuration and cleanup, without opening hardware."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import startup_test as bench
from protocol import ARM, STOP, SET_PARAM, SET_WHEEL_SPEED


class Device:
    def __init__(self, reject_arm=False):
        self.state = 0
        self.params = {}
        self.reject_arm = reject_arm
        self.commands = []

    def request(self, port, kind, payload, seq):
        self.commands.append(kind)
        before = self.state
        if kind == STOP:
            self.state = 0
        elif kind == SET_PARAM:
            param_id, value = struct.unpack('<BI', payload)
            self.params[param_id] = value
        elif kind == ARM and not self.reject_arm:
            self.state = 1
        status = struct.pack('<BHiiiiHHH', before, 0, 0, 0, 0, 0, 0, 0, 0)
        return [(0x80, seq, status)]


class StartupTests(unittest.TestCase):
    def run_test(self, device, wheel, runner):
        with patch.object(bench, 'send_and_read', device.request), patch.object(bench, 'run_motion', runner):
            bench.test_wheel(object(), wheel)

    def test_each_wheel_only_and_cleanup(self):
        for wheel, expected in [('left', (400, 0)), ('right', (0, 400))]:
            device = Device()
            def runner(port, kind, payload, seq, duration):
                self.assertEqual(kind, SET_WHEEL_SPEED)
                self.assertEqual(struct.unpack('<ii', payload), expected)
                self.assertEqual(duration, 1.0)
                self.assertEqual(device.state, 1)
                self.assertEqual(device.params[9], 512)
                self.assertEqual(device.params[10], 50)
                self.assertEqual(device.params[0], 1469)
                self.assertEqual(device.params[1], 1471)
            self.run_test(device, wheel, runner)
            self.assertEqual(device.params[9], 0)
            self.assertEqual(device.state, 0)

    def test_arm_rejected_never_moves(self):
        device = Device(reject_arm=True)
        def runner(*args):
            self.fail('Motion must not be sent')
        with self.assertRaisesRegex(RuntimeError, 'ARM was not confirmed'):
            self.run_test(device, 'left', runner)
        self.assertEqual(device.params[9], 0)
        self.assertEqual(device.state, 0)

    def test_motion_error_or_interrupt_cleans_up(self):
        for error in [RuntimeError('missing telemetry'), KeyboardInterrupt()]:
            device = Device()
            def runner(*args):
                raise error
            with self.assertRaises(type(error)):
                self.run_test(device, 'left', runner)
            self.assertEqual(device.params[9], 0)
            self.assertEqual(device.state, 0)

    def test_stop_reply_loss_still_zeros_limit(self):
        device = Device()
        original = device.request
        def request(port, kind, payload, seq):
            result = original(port, kind, payload, seq)
            if kind == STOP and device.commands.count(STOP) > 1:
                return []
            return result
        with patch.object(bench, 'send_and_read', request), patch.object(bench, 'run_motion'):
            with self.assertRaisesRegex(RuntimeError, 'Cleanup incomplete'):
                bench.test_wheel(object(), 'left')
        self.assertEqual(device.params[9], 0)


if __name__ == '__main__':
    unittest.main()
