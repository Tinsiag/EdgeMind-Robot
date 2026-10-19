from pathlib import Path
import queue
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from control import ControlWorker
from demo import DemoPort
from legacy import ARM, SET_WHEEL_SPEED, CarController, FrameParser, Move
from transport import UdpControlPort, open_control


class RecordingPort(DemoPort):
    def __init__(self):
        super().__init__()
        self.sent = []
        self.wire = FrameParser()

    def write(self, data):
        self.sent.extend(kind for kind, _, _ in self.wire.feed(data))
        return super().write(data)


class ControlTests(unittest.TestCase):
    def wait_event(self, events, kind, timeout=4):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            item = events.get(timeout=max(0.01, end-time.monotonic()))
            if item[0] == kind:
                return item[1]
        self.fail(f'Missing event {kind}')

    def test_connect_does_not_arm(self):
        events, port = queue.Queue(), RecordingPort()
        with patch('control.DemoPort', return_value=port):
            worker = ControlWorker('UART', '', 5000, False, events, demo=True)
            worker.start()
            try:
                self.wait_event(events, 'control_connected')
            finally:
                worker.shutdown()
                worker.join(4)
        self.assertNotIn(ARM, port.sent)
        self.assertNotIn(SET_WHEEL_SPEED, port.sent)
        self.assertFalse(worker.is_alive())

    def test_stop_cancels_queued_move_before_arm(self):
        events, port = queue.Queue(), RecordingPort()
        worker = ControlWorker('UART', '', 5000, False, events, demo=True)
        worker.connected = True
        self.assertTrue(worker.submit('move', Move('forward', 20, 100)))
        worker.stop()
        with patch('control.DemoPort', return_value=port):
            worker.start()
            try:
                self.wait_event(events, 'motion_idle')
            finally:
                worker.shutdown()
                worker.join(4)
        self.assertNotIn(ARM, port.sent)
        self.assertNotIn(SET_WHEEL_SPEED, port.sent)

    def test_cancel_active_move_and_shutdown(self):
        events, port = queue.Queue(), RecordingPort()
        worker = ControlWorker('UART', '', 5000, False, events, demo=True)
        with patch('control.DemoPort', return_value=port):
            worker.start()
            try:
                self.wait_event(events, 'control_connected')
                self.assertTrue(worker.submit('move', Move('forward', 100, 100)))
                end = time.monotonic() + 3
                while SET_WHEEL_SPEED not in port.sent and time.monotonic() < end:
                    time.sleep(0.01)
                self.assertIn(SET_WHEEL_SPEED, port.sent)
                worker.stop()
                self.wait_event(events, 'motion_idle')
                self.assertFalse(port.armed)
                self.assertEqual(port.speeds, [0, 0])
            finally:
                worker.shutdown()
                worker.join(4)
        self.assertFalse(worker.is_alive())

    def test_invalid_move_rejected_before_arm(self):
        port = RecordingPort()
        car = CarController(port)
        with self.assertRaises(ValueError):
            car.move(Move('forward', float('nan')))
        self.assertNotIn(ARM, port.sent)

    def test_loopback_tcp_protocol_and_bridge_detection(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(2)
        halt = threading.Event()
        failures = []

        def server():
            try:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(0.1)
                    port = DemoPort()
                    while not halt.is_set():
                        try:
                            data = conn.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        port.write(data)
                        response = port.read(port.in_waiting) if port.in_waiting else b''
                        if response:
                            conn.sendall(response[:3])
                            conn.sendall(response[3:])
            except Exception as exc:
                failures.append(exc)

        worker = threading.Thread(target=server, daemon=True)
        worker.start()
        port = None
        try:
            port = open_control('TCP', '127.0.0.1', listener.getsockname()[1])
            car = CarController(port, right_motor_reversed=True)
            car.stop()
            self.assertTrue(car.detect_capabilities().bridge_fixed)
            self.assertFalse(car.right_motor_reversed)
            self.assertEqual(car.status().state, 0)
        finally:
            halt.set()
            if port:
                port.close()
            worker.join(3)
            listener.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])

    def test_bad_transport_settings(self):
        for args in [('UDP', 'not-an-ip', 5000), ('UDP', '127.0.0.1', 0),
                     ('TCP', 'not-an-ip', 5000), ('TCP', '127.0.0.1', 0),
                     ('UART', 'socket://127.0.0.1:1', 5000), ('bad', '', 5000)]:
            with self.assertRaises(ValueError):
                open_control(*args)

    def test_udp_control_envelope_matches_session_and_number(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.bind(('127.0.0.1', 0))
        listener.settimeout(2)
        port = UdpControlPort('127.0.0.1', listener.getsockname()[1], 0)
        try:
            request = b'\xaa\x55\x01\x04\x00\x01\xfa\x00\x00\x00'
            port.write(request)
            data, source = listener.recvfrom(2048)
            self.assertEqual(data[:4], b'EMC1')
            self.assertEqual(data[12:-2], request)
            # Same session and sequence are accepted; a wrong session is ignored.
            listener.sendto(data, ('127.0.0.1', port.socket.getsockname()[1]))
            self.assertEqual(port.read(len(request)), request)
            port.socket.sendto(data[:4] + b'\0'*8 + data[12:], port.peer)
            self.assertEqual(port.read(1), b'')
        finally:
            port.close()
            listener.close()


if __name__ == '__main__':
    unittest.main()
