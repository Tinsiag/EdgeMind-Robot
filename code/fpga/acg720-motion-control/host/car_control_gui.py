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
        root.geometry('900x980')
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
        self.reverse_right = tk.BooleanVar(value=False)
        self.legacy_reverse_preference = False
        self.reverse_check = ttk.Checkbutton(body, text='旧 A722 右轮反向补偿（A723 无需勾选，连接前设置）',
                                             variable=self.reverse_right)
        self.reverse_check.pack(anchor='w', pady=(0, 3))
        self.has_vision = False
        self.auto_running = False
        self.vision_buttons = []
        vision_panel = ttk.Frame(body)
        vision_panel.pack(fill='x', pady=5)
        for label, task in [('启动循线', 'line'), ('切换手动', 'manual'), ('查询感知', 'sense')]:
            button = ttk.Button(vision_panel, text=label, command=lambda t=task: self.vision_task(t))
            button.pack(side='left', padx=4)
            self.vision_buttons.append(button)
        self.sensing_text = tk.StringVar(value='视觉功能：连接后自动识别固件')
        ttk.Label(body, textvariable=self.sensing_text, wraplength=820).pack(anchor='w')
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
        self.limit_note = tk.StringVar(value='A723：自动识别右桥修正，启用双轮同步减速与遥测低速稳定检查。\n'
                  '旧 A722 须先勾选右轮补偿；距离/角度按编码器估算，仍需实车标定。\n'
                  '故障不会自动清除，首次请架空核对两轮方向。')
        ttk.Label(body, textvariable=self.limit_note,
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
            widget.configure(state='normal' if self.connected and not self.busy and not self.auto_running and not self.shutdown.is_set() else 'disabled')
        for widget in self.vision_buttons:
            widget.configure(state='normal' if self.connected and self.has_vision and not self.busy and not self.shutdown.is_set() else 'disabled')
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
        self.legacy_reverse_preference = self.reverse_right.get()
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
                capabilities = car.detect_capabilities()
                self.events.put(('capabilities', capabilities))
                self.events.put(('log', str(car.status())))
                self.events.put(('connected', f'{name} 已连接，PWM已归零'))
                self.events.put(('log', f'右轮驱动反向补偿：{"开启" if car.right_motor_reversed else "关闭"}；'
                                 '编码器目标与方向异常检查保持原约定'))
                try:
                    while not self.shutdown.is_set():
                        try:
                            task, data = self.tasks.get(timeout=0.1)
                        except queue.Empty:
                            if car.capabilities is not None and car.capabilities.has_vision:
                                try:
                                    self.events.put(('sensing', car.sensing()))
                                except Exception as exc:
                                    self.events.put(('log', f'感知查询失败：{exc}'))
                            continue
                        try:
                            if task == 'move':
                                self.events.put(('log', f'动作：{data.action}，目标：{data.amount}'
                                                 f'{"厘米" if data.action in ("forward", "backward") else "度"}，'
                                                 f'轮速：{data.speed} mm/s'))
                                done = car.move(data, self.cancel)
                                message = ('行程进入容差且遥测低速稳定，已发送STOP' if car.synchronized_motion
                                           else '编码器目标已达到，已发送STOP') if done else '动作已取消'
                                self.events.put(('log', message))
                            elif task == 'stop':
                                car.stop()
                            elif task == 'line':
                                self.events.put(('sensing', car.start_line(self.cancel)))
                            elif task == 'manual':
                                car.set_mode(False)
                                self.events.put(('sensing', car.sensing()))
                            elif task == 'sense':
                                self.events.put(('sensing', car.sensing()))
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
        if self.connected:
            self.busy = True
            self.controls()
            self.tasks.put(('stop', None))

    def vision_task(self, task):
        if self.connected and self.has_vision and not self.busy:
            self.cancel.clear()
            self.busy = True
            self.controls()
            self.tasks.put((task, None))

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
                    self.auto_running = False
                    self.has_vision = False
                    self.reverse_right.set(self.legacy_reverse_preference)
                    self.state.set('已断开')
                elif kind == 'capabilities':
                    self.has_vision = value is not None and value.has_vision
                    if value is not None and value.bridge_fixed:
                        self.reverse_right.set(False)
                        if self.has_vision:
                            self.speed.set('100')
                            self.limit_note.set(f'新视觉固件：轮速最高 {value.max_speed} mm/s，右桥极性已在 FPGA 修正。\n'
                                                '循线依赖有效摄像头、测距及显示；遇障后人工启动。STOP 为滑行停车。')
                        else:
                            self.speed.set('200')
                            self.sensing_text.set('运动固件：右桥已修正 · 双轮同步减速 · 无视觉功能')
                            self.limit_note.set('新运动固件：右桥极性已在 FPGA 的 PI 之后修正。\n'
                                                '直线和转向使用双轮同步减速，停止后检查遥测低速稳定。STOP 为滑行停车。')
                    else:
                        self.sensing_text.set('旧版运动固件：保留原右轮补偿，视觉按钮不可用')
                elif kind == 'sensing':
                    self.auto_running = value.mode == 1 and value.armed
                    self.sensing_text.set(f'{"循线" if value.mode else "手动"} · '
                                          f'前沿净空 {value.clearance_mm} mm · 原始距离 {value.distance_mm} mm · '
                                          f'黑线 {value.near_center}/{value.far_center} 有效区 {value.regions_valid} · '
                                          f'{value.stop_reason} · 数据年龄 {value.line_age_ms}/{value.tof_age_ms} ms')
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
