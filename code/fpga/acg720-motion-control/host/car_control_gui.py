"""Tk desktop controller. Launch with: python host/car_control_gui.py"""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from serial.tools import list_ports
from serial_control import open_serial
from car_control import CarController, Move


class CarApp:
    def __init__(self, root):
        self.root = root
        self.events, self.tasks = queue.Queue(), queue.Queue()
        self.cancel, self.shutdown = threading.Event(), threading.Event()
        self.connected = self.busy = self.closing = False
        self.worker = None
        root.title('EdgeMind 小车控制台')
        root.geometry('840x800')
        root.minsize(800, 740)
        root.configure(bg='#eef3f8')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background='#eef3f8')
        style.configure('TLabel', background='#eef3f8', font=('Microsoft YaHei UI', 10))
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=8)
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 21, 'bold'), foreground='#15364c')
        body = ttk.Frame(root, padding=22)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='EdgeMind · 小车控制', style='Title.TLabel').pack(anchor='w')
        ttk.Label(body, text='按距离前进 / 后退 · 按角度原地左转 / 右转').pack(anchor='w', pady=(4, 15))
        connection = ttk.Frame(body)
        connection.pack(fill='x')
        ttk.Label(connection, text='串口').pack(side='left')
        self.port = tk.StringVar(value='COM4')
        self.port_box = ttk.Combobox(connection, textvariable=self.port, width=12)
        self.port_box.pack(side='left', padx=8)
        self.refresh_button = ttk.Button(connection, text='刷新', command=self.refresh)
        self.refresh_button.pack(side='left')
        self.connect_button = ttk.Button(connection, text='连接', command=self.connect)
        self.connect_button.pack(side='left', padx=8)
        self.disconnect_button = ttk.Button(connection, text='断开', command=self.disconnect)
        self.disconnect_button.pack(side='left')
        self.state = tk.StringVar(value='未连接 · 连接不会启动电机')
        ttk.Label(body, textvariable=self.state, foreground='#17677b').pack(anchor='w', pady=12)
        settings = ttk.Frame(body)
        settings.pack(fill='x', pady=8)
        self.speed = tk.StringVar(value='200')
        ttk.Label(settings, text='轮速 mm/s（40～400）').pack(side='left')
        self.speed_entry = ttk.Entry(settings, textvariable=self.speed, width=8)
        self.speed_entry.pack(side='left', padx=10)
        ttk.Label(settings, text='输出最高 50% · 每次只执行一个动作').pack(side='left')
        self.reverse_right = tk.BooleanVar(value=True)
        self.reverse_check = ttk.Checkbutton(body, text='右轮驱动反向补偿（当前小车默认开启，连接前设置）',
                                             variable=self.reverse_right)
        self.reverse_check.pack(anchor='w', pady=(0, 3))
        self.distance = tk.StringVar(value='20')
        self.angle = tk.StringVar(value='90')
        self.motion_buttons = []
        self.inputs = [self.speed_entry]
        self.row(body, '直线距离（厘米）', self.distance, (10, 20, 50, 100),
                 [('前进 ↑', 'forward'), ('后退 ↓', 'backward')])
        self.row(body, '旋转角度（度）', self.angle, (15, 45, 90, 180),
                 [('左转 ↶', 'left'), ('右转 ↷', 'right')])
        self.stop_button = tk.Button(body, text='停止  SPACE', command=self.stop,
                                     bg='#c83e4d', fg='white', activebackground='#9e2937',
                                     font=('Microsoft YaHei UI', 14, 'bold'), pady=9)
        self.stop_button.pack(fill='x', pady=(16, 8))
        root.bind('<space>', self.space_stop)
        ttk.Label(body, text='距离/角度按编码器估算；滑行、打滑会影响实际位置。\n'
                  '右轮反向补偿仅改主机目标，右轮轮速闭环未修正，可能到达50%限幅。\n'
                  '现有编码器故障会阻止运行，不自动清故障。首次请架空核对两轮方向。',
                  foreground='#775a2c').pack(anchor='w', pady=5)
        self.log = tk.Text(body, height=9, wrap='word', font=('Consolas', 10),
                           bg='#132b3a', fg='#dbeaf2', relief='flat', padx=10, pady=8)
        self.log.pack(fill='both', expand=True, pady=(8, 0))
        self.log.configure(state='disabled')
        self.refresh()
        self.controls()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(60, self.pump)

    def row(self, parent, title, variable, presets, actions):
        panel = ttk.LabelFrame(parent, text=title, padding=12)
        panel.pack(fill='x', pady=7)
        entry = ttk.Entry(panel, textvariable=variable, width=9)
        entry.pack(side='left', padx=(0, 8))
        self.inputs.append(entry)
        for value in presets:
            button = ttk.Button(panel, text=str(value), width=4,
                                command=lambda n=value: variable.set(str(n)))
            button.pack(side='left', padx=2)
            self.inputs.append(button)
        for label, action in actions:
            button = ttk.Button(panel, text=label, command=lambda a=action: self.move(a))
            button.pack(side='left', padx=5)
            self.motion_buttons.append(button)

    def refresh(self):
        self.port_box['values'] = [p.device for p in list_ports.comports()]

    def controls(self):
        for widget in self.motion_buttons:
            widget.configure(state='normal' if self.connected and not self.busy and not self.shutdown.is_set() else 'disabled')
        for widget in self.inputs:
            widget.configure(state='disabled' if self.busy else 'normal')
        self.connect_button.configure(state='disabled' if self.worker and self.worker.is_alive() else 'normal')
        self.port_box.configure(state='disabled' if self.worker and self.worker.is_alive() else 'normal')
        self.disconnect_button.configure(state='normal' if self.worker and self.worker.is_alive() else 'disabled')
        self.reverse_check.configure(state='disabled' if self.worker and self.worker.is_alive() else 'normal')

    def connect(self):
        name = self.port.get().strip()
        if not name:
            messagebox.showerror('串口', '请选择串口')
            return
        self.cancel.clear()
        self.shutdown.clear()
        self.tasks = queue.Queue()
        self.state.set('正在连接…')
        self.worker = threading.Thread(target=self.serial_worker,
                                       args=(name, self.reverse_right.get()), daemon=True)
        self.worker.start()
        self.controls()

    def serial_worker(self, name, reverse_right):
        try:
            with open_serial(name) as port:
                port.timeout = 0.02
                car = CarController(port, lambda value: self.events.put(('log', str(value))),
                                    right_motor_reversed=reverse_right)
                car.stop()
                self.events.put(('log', str(car.status())))
                self.events.put(('connected', f'{name} 已连接，PWM已归零'))
                self.events.put(('log', f'右轮驱动反向补偿：{"开启" if reverse_right else "关闭"}；'
                                 '编码器目标与方向异常检查保持原约定'))
                try:
                    while not self.shutdown.is_set():
                        try:
                            task, data = self.tasks.get(timeout=0.1)
                        except queue.Empty:
                            continue
                        try:
                            if task == 'move':
                                self.events.put(('log', f'动作：{data.action}，目标：{data.amount}'
                                                 f'{"厘米" if data.action in ("forward", "backward") else "度"}，'
                                                 f'轮速：{data.speed} mm/s'))
                                done = car.move(data, self.cancel)
                                self.events.put(('log', '编码器目标已达到，已发送STOP' if done else '动作已取消'))
                            elif task == 'stop':
                                car.stop()
                        except Exception as exc:
                            self.events.put(('log', str(exc)))
                        finally:
                            self.events.put(('done', None))
                finally:
                    car.stop()
        except Exception as exc:
            self.events.put(('log', f'连接/停车错误：{exc}'))
        finally:
            self.events.put(('disconnected', None))

    def move(self, action):
        if not self.connected or self.busy or self.shutdown.is_set():
            return
        try:
            amount = float(self.distance.get() if action in ('forward', 'backward') else self.angle.get())
            move = Move(action, amount, int(self.speed.get()))
            move.targets()
        except ValueError as exc:
            messagebox.showerror('参数无效', str(exc))
            return
        self.cancel.clear()
        self.busy = True
        self.state.set('执行中… 可随时按停止或空格')
        self.controls()
        self.tasks.put(('move', move))

    def stop(self):
        self.cancel.set()
        if self.connected and not self.busy:
            self.busy = True
            self.controls()
            self.tasks.put(('stop', None))

    def space_stop(self, event):
        self.stop()
        return 'break'

    def disconnect(self):
        self.cancel.set()
        self.shutdown.set()
        self.state.set('正在停止并断开…')
        self.controls()

    def close(self):
        self.closing = True
        self.disconnect()
        if not self.worker or not self.worker.is_alive():
            self.root.destroy()

    def pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'connected':
                    self.connected = True
                    self.state.set(value)
                elif kind == 'done':
                    self.busy = False
                    self.state.set('动作结束 · 查看下方状态记录')
                elif kind == 'disconnected':
                    self.connected = self.busy = False
                    self.state.set('已断开')
                if kind == 'log':
                    self.log.configure(state='normal')
                    self.log.insert('end', value + '\n')
                    self.log.see('end')
                    self.log.configure(state='disabled')
        except queue.Empty:
            pass
        self.controls()
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
        else:
            self.root.after(60, self.pump)


def main():
    root = tk.Tk()
    CarApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
