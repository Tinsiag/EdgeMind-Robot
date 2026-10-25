from pathlib import Path
import sys
import time
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from app import CameraCarApp


class AppTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = CameraCarApp(self.root, demo=True)
        self.root.title('EdgeMind automated UI verification')
        self.root.geometry('1280x820-3000+0')
        self.root.deiconify()

    def cycle_until(self, predicate, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.fail('GUI condition timed out')

    def tearDown(self):
        self.app.close()
        end = time.monotonic() + 4
        while self.root.tk.call('info', 'commands', '.') and time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app.control and self.app.control.is_alive())

    def test_layout_default_and_minimum_size(self):
        for size in ('1280x820', '1060x740'):
            self.root.geometry(size + '-3000+0')
            self.root.update()
            for widget in [self.app.canvas, self.app.log, self.app.stop_button,
                           self.app.capture_button, self.app.clear_button] + self.app.move_buttons:
                self.assertTrue(widget.winfo_ismapped())
                x = widget.winfo_rootx() - self.root.winfo_rootx()
                y = widget.winfo_rooty() - self.root.winfo_rooty()
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + widget.winfo_width(), self.root.winfo_width())
                self.assertLessEqual(y + widget.winfo_height(), self.root.winfo_height())
            self.assertGreaterEqual(self.app.canvas.winfo_height(), 200)
            self.assertGreaterEqual(self.app.log.winfo_height(), 70)

    def test_simulated_move_completes_and_disconnects_without_hardware(self):
        with patch('control.open_control', side_effect=AssertionError('Must not open hardware')):
            self.cycle_until(lambda: self.app.connected)
            self.app.move('forward')
            self.cycle_until(lambda: not self.app.busy, timeout=7)
            log = self.app.log.get('1.0', 'end')
            self.assertIn('动作完成', log)
            self.assertNotIn('错误', log)
            self.assertGreater(int(self.app.metrics['编码器 L / R'].get().split('/')[0]), 1000)
            self.app.disconnect()
            self.cycle_until(lambda: not self.app.control.is_alive())

    def test_space_cancels_motion(self):
        self.cycle_until(lambda: self.app.connected)
        self.app.distance.set('100')
        self.app.move('forward')
        self.cycle_until(lambda: self.app.metrics['PWM L / R'].get() != '0 / 0', timeout=10)
        self.assertEqual(self.app.key_stop(None), 'break')
        self.cycle_until(lambda: not self.app.busy and self.app.metrics['PWM L / R'].get() == '0 / 0')
        self.assertEqual(self.app.control.cancel.is_set(), True)
        self.assertEqual(self.app.metrics['PWM L / R'].get(), '0 / 0')


if __name__ == '__main__':
    unittest.main()
