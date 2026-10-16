"""Mock serial tests: no hardware is opened, no physical motion is requested."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import serial_control as ctl
from protocol import frame, SET_TWIST, ROTATE, STOP, HEARTBEAT, GET_STATUS

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

if __name__=='__main__':unittest.main()
