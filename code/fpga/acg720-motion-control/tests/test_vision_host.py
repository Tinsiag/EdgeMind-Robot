"""Vision protocol and bridge capability negotiation; no physical serial IO."""
import struct
import sys
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from protocol import (Capabilities, GET_CAPABILITIES, GET_SENSING, FrameParser,
                      decode_capabilities, decode_sensing, frame)
from car_control import CarController, Move


class VisionHostTests(unittest.TestCase):
    def test_capabilities_disable_compensation(self):
        car = CarController(object())
        with patch('car_control.send_and_read', return_value=[(0xC0, 1, b'EVM1' + struct.pack('<HH', 15, 150))]):
            cap = car.detect_capabilities()
        self.assertTrue(cap.bridge_fixed)
        self.assertFalse(car.right_motor_reversed)

    def test_old_firmware_keeps_compensation(self):
        car = CarController(object())
        with patch('car_control.send_and_read', return_value=[]):
            self.assertIsNone(car.detect_capabilities())
        self.assertTrue(car.right_motor_reversed)

    def test_wrong_seq_does_not_disable_compensation(self):
        car = CarController(object())
        with patch('car_control.send_and_read', return_value=[(0xC0, 9, b'EVM1' + struct.pack('<HH', 15, 150))]):
            self.assertIsNone(car.detect_capabilities())
        self.assertTrue(car.right_motor_reversed)

    def test_bad_signature_rejected(self):
        with self.assertRaises(ValueError):
            decode_capabilities(b'NOPE' + struct.pack('<HH', 15, 150))

    def test_sensing_wire_format(self):
        payload = struct.pack('<BBHHBBHHHHBBHIIHH', 3, 2, 240, 220, 9, 0x12,
                              12, 40, 390, 410, 3, 0, 123, 10, 20, 512, 0)
        value = decode_sensing(payload)
        self.assertTrue(value.armed)
        self.assertEqual(value.mode, 1)
        self.assertEqual(value.clearance_mm, 220)
        self.assertEqual(value.left_invalid, 10)
        self.assertEqual(value.stop_reason, '前方障碍')

    def test_new_firmware_speed_checked_before_io(self):
        car = CarController(object())
        car.capabilities = Capabilities(15, 150)
        with self.assertRaises(ValueError):
            car.move(Move('forward', 10, 200))

    def test_version_is_validated(self):
        packet = bytearray(frame(GET_SENSING))
        packet[2] = 2
        from protocol import crc16_ccitt
        packet[-2:] = struct.pack('<H', crc16_ccitt(packet[2:-2]))
        self.assertEqual(FrameParser().feed(bytes(packet)), [])

    def test_vision_error_does_not_fallback_to_legacy_sign(self):
        car = CarController(object())
        car.capabilities = Capabilities(15, 150)
        car.right_motor_reversed = False
        with patch('car_control.send_and_read', return_value=[]):
            with self.assertRaises(RuntimeError):
                car.sensing()
        self.assertFalse(car.right_motor_reversed)

    def test_cancelled_start_never_sends_start(self):
        car = CarController(object())
        car.capabilities = Capabilities(15, 150)
        cancel = threading.Event()
        cancel.set()
        with patch.object(car, 'stop') as stopped, patch.object(car, 'sensing', return_value='stopped'), patch.object(car, 'request') as request:
            self.assertEqual(car.start_line(cancel), 'stopped')
            stopped.assert_called_once()
            request.assert_not_called()

    def test_cancel_after_mode_switch_never_sends_start(self):
        car = CarController(object())
        car.capabilities = Capabilities(15, 150)
        cancel = threading.Event()
        with patch.object(car, 'set_mode', side_effect=lambda _: cancel.set()), patch.object(car, 'stop'), patch.object(car, 'sensing', return_value='stopped'), patch.object(car, 'request') as request:
            self.assertEqual(car.start_line(cancel), 'stopped')
            request.assert_not_called()

    def test_uncertain_start_attempts_stop(self):
        car = CarController(object())
        with patch.object(car, '_start_line', side_effect=RuntimeError('telemetry lost')), patch.object(car, 'stop') as stopped:
            with self.assertRaisesRegex(RuntimeError, 'telemetry lost'):
                car.start_line()
            stopped.assert_called_once()


if __name__ == '__main__':
    unittest.main()
