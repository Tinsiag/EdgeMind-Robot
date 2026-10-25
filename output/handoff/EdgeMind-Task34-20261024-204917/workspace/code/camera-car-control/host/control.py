"""One worker owns the transport; cancellation also covers queued moves."""
import queue
import threading
import time

from demo import DemoPort
from legacy import CarController, CLEAR_FAULT, Status
from transport import open_control


class ControlWorker(threading.Thread):
    def __init__(self, mode, address, tcp_port, reverse_right, events, demo=False):
        super().__init__(daemon=True, name='motion-link')
        self.mode, self.address, self.tcp_port = mode, address, tcp_port
        self.reverse_right, self.events, self.demo = reverse_right, events, demo
        self.commands = queue.Queue(maxsize=4)
        self.halt = threading.Event()
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.busy = self.connected = False

    def notify(self, value):
        self.events.put(('telemetry' if isinstance(value, Status) else 'log', value))

    def submit(self, name, value=None):
        with self.lock:
            if self.halt.is_set() or not self.connected or self.busy:
                return False
            self.cancel = threading.Event()
            self.busy = True
            self.commands.put_nowait((name, value, self.cancel))
            return True

    def stop(self):
        with self.lock:
            self.cancel.set()
            self.busy = True
            while True:
                try:
                    self.commands.get_nowait()
                except queue.Empty:
                    break
            self.commands.put_nowait(('stop', None, self.cancel))

    def shutdown(self):
        self.halt.set()
        self.stop()

    def run(self):
        port, car = None, None
        try:
            port = DemoPort() if self.demo else open_control(self.mode, self.address, self.tcp_port)
            car = CarController(port, self.notify, right_motor_reversed=self.reverse_right)
            car.stop()
            capabilities = car.detect_capabilities()
            status = car.status()
            self.notify(status)
            if self.halt.is_set():
                return
            self.connected = True
            self.events.put(('control_connected', (capabilities, car.right_motor_reversed)))
            next_poll = time.monotonic()
            while not self.halt.is_set():
                try:
                    name, value, cancel = self.commands.get(timeout=0.05)
                except queue.Empty:
                    if time.monotonic() >= next_poll:
                        self.notify(car.status())
                        next_poll = time.monotonic() + 0.2
                    continue
                try:
                    if name == 'move':
                        result = car.move(value, cancel)
                        self.events.put(('log', '动作完成' if result else '动作已取消'))
                    elif name == 'stop':
                        car.stop()
                        self.events.put(('log', '已确认 PWM 归零'))
                    elif name == 'clear_fault' and not cancel.is_set():
                        car.stop()
                        status = car.request(CLEAR_FAULT)
                        self.notify(status)
                        if status.faults:
                            raise RuntimeError(f'故障仍存在：0x{status.faults:04X}')
                        self.events.put(('log', '故障已清除，保持停止'))
                    self.notify(car.status())
                except Exception as exc:
                    self.events.put(('error', str(exc)))
                    # A failed operation must prove a stopped link before reuse.
                    car.stop()
                finally:
                    with self.lock:
                        self.busy = not self.commands.empty()
                    self.events.put(('motion_idle', None))
        except Exception as exc:
            self.events.put(('error', f'控制连接失败或中断：{exc}'))
        finally:
            self.connected = False
            if car is not None:
                try:
                    car.stop()
                except Exception as exc:
                    self.events.put(('error', f'停车未确认：{exc}'))
            if port is not None:
                port.close()
            self.events.put(('control_disconnected', None))
