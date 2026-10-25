"""Mock serial tests: no hardware is opened, no physical motion is requested."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import serial_control as ctl
from protocol import frame, SET_TWIST, ROTATE, STOP, HEARTBEAT, GET_STATUS
from car_control import CarController, Move, count_delta
from protocol import Status, ARM, SET_PARAM
import threading

class Clock:
    def __init__(self): self.t=0.0
    def monotonic(self): self.t+=0.001; return self.t
    def sleep(self, seconds): self.t+=seconds

class Port:
    timeout=0.2
    def __init__(self, failure=None, state=2):
        self.writes=[]; self.failure=failure; self.state=state; self.buffer=b''; self.flushed=False
    @property
    def in_waiting(self): return len(self.buffer)
    def write(self, packet):
        kind=packet[3]
        if self.failure and len(self.writes)==1 and kind!=STOP:
            error=self.failure;self.failure=None;raise error
        self.writes.append(packet)
        if kind==GET_STATUS:
            payload=struct.pack('<BHiiiiHHH',self.state,0,0,0,0,0,0,0,0)
            self.buffer=frame(0x80,payload,packet[5],0)
        return len(packet)
    def read(self,n):
        data=self.buffer[:n];self.buffer=self.buffer[n:];return data
    def flush(self): self.flushed=True

class MotionTests(unittest.TestCase):
    def test_old_stop_reply_does_not_hide_current_status(self):
        payload=struct.pack('<BHiiiiHHH',0,0,0,0,0,0,0,0,0)
        chunks=[frame(0x80,payload,seq=99),frame(0x80,payload,seq=7)]
        port=Port()
        port.write=lambda packet:len(packet)
        port.read=lambda n:chunks.pop(0) if chunks else b''
        clock=Clock()
        with patch.object(ctl.time,'monotonic',clock.monotonic):
            packets=ctl.send_and_read(port,GET_STATUS,b'',7)
        self.assertEqual([p[1] for p in packets],[99,7])

    def test_old_reply_alone_does_not_count_as_current_reply(self):
        payload=struct.pack('<BHiiiiHHH',0,0,0,0,0,0,0,0,0)
        chunks=[frame(0x80,payload,seq=99)]
        port=Port()
        port.write=lambda packet:len(packet)
        port.read=lambda n:chunks.pop(0) if chunks else b''
        clock=Clock()
        with patch.object(ctl.time,'monotonic',clock.monotonic):
            packets=ctl.send_and_read(port,GET_STATUS,b'',7,0.01)
        self.assertFalse(any(p[1]==7 for p in packets))

    def run_with_clock(self, port, kind=SET_TWIST, duration=0.2):
        clock=Clock()
        with patch.object(ctl.time,'monotonic',clock.monotonic),patch.object(ctl.time,'sleep',clock.sleep):
            ctl.run_motion(port,kind,b'\0'*8,1,duration)
    def assert_stopped(self, port):
        self.assertEqual(port.writes[-1][3],STOP)
        self.assertTrue(port.flushed)
        self.assertEqual(port.timeout,0.2)
    def test_normal_exit(self):
        port=Port();self.run_with_clock(port);self.assert_stopped(port)
    def test_keyboard_interrupt(self):
        port=Port(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt): self.run_with_clock(port)
        self.assert_stopped(port)
    def test_serial_exception(self):
        port=Port(ctl.serial.SerialException('mock disconnect'))
        with self.assertRaises(ctl.serial.SerialException): self.run_with_clock(port)
        self.assert_stopped(port)
    def test_fault_or_disarmed_exit(self):
        for state in [0,3]:
            port=Port(state=state)
            # FAULT reports a fault bit, independent of its state code.
            if state==3:
                original=port.write
                def write(packet):
                    result=original(packet)
                    if packet[3]==GET_STATUS:
                        port.buffer=frame(0x80,struct.pack('<BHiiiiHHH',3,2,0,0,0,0,0,0,0),packet[5],0)
                    return result
                port.write=write
            with self.assertRaises(RuntimeError):self.run_with_clock(port)
            self.assert_stopped(port)
    def test_rotate_once_and_heartbeat(self):
        port=Port(state=1);self.run_with_clock(port,ROTATE,1.0)
        types=[p[3] for p in port.writes]
        self.assertEqual(types.count(ROTATE),1)
        self.assertIn(HEARTBEAT,types)
        self.assert_stopped(port)
    def test_missing_status_stops(self):
        port=Port()
        port.read=lambda n:b''
        clock=Clock()
        with self.assertRaises(RuntimeError):self.run_with_clock(port)
        self.assert_stopped(port)
    def test_stop_delivery_failure_is_reported(self):
        port=Port()
        original=port.write
        def write(packet):
            if packet[3]==STOP: raise ctl.serial.SerialException('STOP disconnected')
            return original(packet)
        port.write=write
        import io
        out=io.StringIO()
        with patch.object(ctl.sys,'stderr',out):self.run_with_clock(port)
        self.assertIn('STOP delivery failed',out.getvalue())
        self.assertEqual(port.timeout,0.2)

class SimulatedCar(CarController):
    """Deterministic wheel feedback model, without serial or real time."""
    def __init__(self, mode='normal', initial=0, reverse_right=False):
        self.now = 0.0
        self.mode = mode
        self.current_state = 0
        self.counts = [initial, initial]
        self.velocities = (0, 0)
        self.writes = []
        self.params = {}
        self.moving_polls = 0
        self.closed_stop = False
        self.physical_right_reversed = reverse_right
        super().__init__(self, clock=lambda: self.now, sleep=self.advance,
                         right_motor_reversed=reverse_right)

    def advance(self, duration):
        self.now += duration

    def write(self, packet):
        self.writes.append(packet)
        self.velocities = struct.unpack('<ii', packet[8:16])
        self.current_state = 2

    def request(self, kind, payload=b''):
        if kind == STOP:
            self.current_state = 0
            self.velocities = (0, 0)
            self.closed_stop = True
        elif kind == SET_PARAM:
            key, value = struct.unpack('<BI', payload)
            self.params[key] = value
        elif kind == ARM:
            self.current_state = 0 if self.mode == 'reject_arm' else 1
        elif kind == GET_STATUS and self.current_state == 2:
            self.moving_polls += 1
            if self.mode == 'disconnect':
                raise RuntimeError('No telemetry')
            if self.mode != 'stuck':
                for i, speed in enumerate(self.velocities):
                    sign = 1 if speed > 0 else -1 if speed < 0 else 0
                    if i == 1 and self.physical_right_reversed:
                        sign *= -1
                    if self.mode == 'wrong_direction':
                        sign *= -1
                    self.counts[i] = count_delta(self.counts[i] + sign * (50 if i == 0 else 35), 0)
        faults = 2 if self.mode == 'fault' and self.moving_polls else 0
        if faults:
            self.current_state = 3
        return Status(self.current_state, faults, *self.counts, 0, 0, 0, 0, 0)


class RelativeMoveTests(unittest.TestCase):
    def test_reversed_right_bridge_all_actions_and_stop(self):
        for action, packet_signs in [('forward', (1, -1)), ('backward', (-1, 1)),
                                     ('left', (-1, -1)), ('right', (1, 1))]:
            car = SimulatedCar(reverse_right=True)
            self.assertTrue(car.move(Move(action, 10)))
            first = struct.unpack('<ii', car.writes[0][8:16])
            self.assertEqual(tuple(1 if n > 0 else -1 for n in first), packet_signs)
            expected = Move(action, 10).targets()
            self.assertEqual(tuple(1 if n > 0 else -1 for n in car.counts),
                             tuple(1 if n > 0 else -1 for n in expected))
            self.assertEqual(car.current_state, 0)
            self.assertEqual(car.params[9], 0)

    def test_compensation_keeps_wrong_direction_check(self):
        car = SimulatedCar(mode='wrong_direction', reverse_right=True)
        with self.assertRaisesRegex(RuntimeError, '编码器方向'):
            car.move(Move('forward', 10))
        self.assertEqual(car.current_state, 0)
        self.assertEqual(car.params[9], 0)

    def test_units_and_turn_signs(self):
        self.assertEqual(Move('forward', 10).targets(), (705, 706))
        self.assertEqual(Move('backward', 10).targets(), (-705, -706))
        left, right = Move('left', 90).targets()
        self.assertLess(left, 0)
        self.assertGreater(right, 0)
        self.assertEqual(Move('right', 90).targets(), (-left, -right))

    def test_bad_input_never_writes(self):
        for move in [Move('forward', 0), Move('forward', float('nan')),
                     Move('left', float('inf')), Move('right', 361),
                     Move('backward', 201), Move('forward', 10, 401),
                     Move('forward', 0.0001)]:
            car = SimulatedCar()
            with self.assertRaises(ValueError):
                car.move(move)
            self.assertEqual(car.params, {})
            self.assertEqual(car.writes, [])

    def test_all_directions_complete_and_cleanup(self):
        for action, signs in [('forward', (1, 1)), ('backward', (-1, -1)),
                              ('left', (-1, 1)), ('right', (1, -1))]:
            car = SimulatedCar()
            self.assertTrue(car.move(Move(action, 10)))
            first = struct.unpack('<ii', car.writes[0][8:16])
            self.assertEqual(tuple(1 if n > 0 else -1 for n in first), signs)
            self.assertEqual(car.params[9], 0)
            self.assertEqual(car.current_state, 0)
            for packet in car.writes:
                self.assertLessEqual(max(abs(n) for n in struct.unpack('<ii', packet[8:16])), 200)

    def test_one_wheel_reached_is_not_restarted(self):
        car = SimulatedCar()
        car.move(Move('forward', 10))
        pairs = [struct.unpack('<ii', p[8:16]) for p in car.writes]
        self.assertTrue(any(left == 0 and right > 0 for left, right in pairs))
        first_zero = next(i for i, (left, _) in enumerate(pairs) if left == 0)
        self.assertTrue(all(left == 0 for left, _ in pairs[first_zero:]))

    def test_fault_disconnect_direction_timeout_stop(self):
        for mode in ['fault', 'disconnect', 'wrong_direction', 'stuck', 'reject_arm']:
            car = SimulatedCar(mode)
            with self.assertRaises(RuntimeError):
                car.move(Move('forward', 10))
            self.assertEqual(car.params[9], 0)
            if mode == 'reject_arm':
                self.assertEqual(car.writes, [])

    def test_cancel_before_arm_and_during_motion(self):
        cancel = threading.Event()
        cancel.set()
        car = SimulatedCar()
        self.assertFalse(car.move(Move('forward', 10), cancel))
        self.assertEqual(car.writes, [])
        cancel.clear()
        car = SimulatedCar()
        car.sleep = lambda seconds: cancel.set()
        self.assertFalse(car.move(Move('forward', 10), cancel))
        self.assertEqual(car.params[9], 0)
        self.assertEqual(car.current_state, 0)

    def test_counter_wrap(self):
        self.assertEqual(count_delta(-2147483640, 2147483640), 16)
        car = SimulatedCar(initial=2147483640)
        self.assertTrue(car.move(Move('forward', 10)))


if __name__=='__main__':unittest.main()
