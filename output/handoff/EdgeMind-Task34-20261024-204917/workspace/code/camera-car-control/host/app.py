"""Camera preview and calibrated ACG720 car control in one desktop window."""
import argparse
import ipaddress
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk
from serial.tools import list_ports

from control import ControlWorker
from demo import scene
from legacy import Move
from video import VideoReceiver

ROOT = Path(__file__).resolve().parents[1]
STATE_NAMES = {0: '停止', 1: '已使能', 2: '运动中', 3: '故障', 4: '旋转中'}


class CameraCarApp:
    def __init__(self, root, demo=False):
        self.root, self.demo = root, demo
        self.events, self.frames = queue.Queue(), queue.Queue(maxsize=1)
        self.control = self.video = None
        self.connected = self.busy = self.closing = False
        self.last_frame = self.last_frame_at = self.photo = None
        self.frame_count = self.demo_index = 0
        self.fps_at = time.monotonic()
        self.shown_frames = 0
        self.fps = 0.0
        self.max_speed = 400
        root.title('EdgeMind | 摄像头与小车控制' + (' | 模拟模式' if demo else ''))
        root.geometry('1280x820')
        root.minsize(1060, 740)
        root.configure(bg='#edf0f2')
        self.styles()
        self.build()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<space>', self.key_stop)
        root.bind('<Escape>', self.key_stop)
        root.after(40, self.pump)
        if demo:
            self.mode.set('UDP')
            self.address.set('127.0.0.1')
            self.source_ip.set('127.0.0.1')
            root.after(100, self.connect)
            root.after(100, self.start_video)

    def styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10), background='#edf0f2', foreground='#233233')
        style.configure('TFrame', background='#edf0f2')
        style.configure('TLabel', background='#edf0f2')
        style.configure('TButton', padding=(10, 7))
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 18, 'bold'))
        style.configure('Metric.TLabel', font=('Consolas', 14, 'bold'))
        style.configure('Accent.TButton', background='#157b69', foreground='white')
        style.map('Accent.TButton', background=[('active', '#106454')])
        style.configure('TLabelframe', background='#edf0f2')
        style.configure('TLabelframe.Label', background='#edf0f2', foreground='#52636a')

    def build(self):
        body = ttk.Frame(self.root, padding=18)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        header = ttk.Frame(body)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(header, text='EdgeMind', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='摄像头 / 小车控制', foreground='#58696c').pack(side='left', padx=18)
        self.link_state = tk.StringVar(value='控制未连接')
        ttk.Label(header, textvariable=self.link_state, foreground='#157b69').pack(side='right')
        if self.demo:
            ttk.Label(header, text='模拟模式', foreground='#a45d10').pack(side='right', padx=20)

        links = ttk.Frame(body)
        links.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(links, text='控制链路').grid(row=0, column=0, padx=(0, 8))
        self.mode = tk.StringVar(value='UDP')
        self.mode_box = ttk.Combobox(links, textvariable=self.mode, values=('UDP', 'UART', 'TCP'), width=6, state='readonly')
        self.mode_box.grid(row=0, column=1)
        self.mode_box.bind('<<ComboboxSelected>>', self.mode_changed)
        found = [p.device for p in list_ports.comports()]
        self.address = tk.StringVar(value='192.168.0.2')
        self.address_box = ttk.Combobox(links, textvariable=self.address, values=found, width=18)
        self.address_box.grid(row=0, column=2, padx=8)
        self.tcp_port = tk.StringVar(value='5000')
        ttk.Label(links, text='网口端口').grid(row=0, column=3)
        self.tcp_entry = ttk.Entry(links, textvariable=self.tcp_port, width=7)
        self.tcp_entry.grid(row=0, column=4, padx=8)
        self.reverse = tk.BooleanVar(value=False)
        self.reverse_box = ttk.Checkbutton(links, text='旧固件右轮补偿', variable=self.reverse)
        self.reverse_box.grid(row=0, column=5, padx=8)
        self.connect_button = ttk.Button(links, text='连接控制', style='Accent.TButton', command=self.connect)
        self.connect_button.grid(row=0, column=6, padx=8)
        self.disconnect_button = ttk.Button(links, text='断开', command=self.disconnect)
        self.disconnect_button.grid(row=0, column=7)
        links.columnconfigure(8, weight=1)

        main = ttk.Frame(body)
        main.grid(row=2, column=0, sticky='nsew')
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0, minsize=310)
        main.rowconfigure(0, weight=1)
        camera = ttk.Frame(main)
        camera.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
        camera.columnconfigure(0, weight=1)
        camera.rowconfigure(2, weight=1)
        camera_head = ttk.Frame(camera)
        camera_head.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(camera_head, text='实时画面', font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left')
        self.camera_state = tk.StringVar(value='未接收')
        ttk.Label(camera_head, textvariable=self.camera_state, foreground='#58696c').pack(side='right')
        video_links = ttk.Frame(camera)
        video_links.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        self.source_ip = tk.StringVar(value='192.168.0.2')
        self.bind_ip = tk.StringVar(value='0.0.0.0')
        self.video_port = tk.StringVar(value='6102')
        self.video_entries = []
        for column, (label, variable, width) in enumerate((('FPGA IP', self.source_ip, 14),
                                                         ('本机 IP', self.bind_ip, 13),
                                                         ('UDP 端口', self.video_port, 6))):
            ttk.Label(video_links, text=label).grid(row=0, column=2*column, padx=(0, 5))
            entry = ttk.Entry(video_links, textvariable=variable, width=width)
            entry.grid(row=0, column=2*column+1, padx=(0, 9))
            self.video_entries.append(entry)
        self.video_button = ttk.Button(video_links, text='接收', command=self.toggle_video)
        self.video_button.grid(row=0, column=6)
        self.canvas = tk.Canvas(camera, background='#182724', highlightthickness=0, width=660, height=396)
        self.canvas.grid(row=2, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda event: self.draw_frame())
        video_footer = ttk.Frame(camera)
        video_footer.grid(row=3, column=0, sticky='ew', pady=8)
        self.video_info = tk.StringVar(value='EMV1 / RGB565')
        ttk.Label(video_footer, textvariable=self.video_info, foreground='#58696c').pack(side='left')
        self.capture_button = ttk.Button(video_footer, text='保存画面', command=self.snapshot)
        self.capture_button.pack(side='right')

        side = ttk.Frame(main, width=310)
        side.grid(row=0, column=1, sticky='nsew')
        ttk.Label(side, text='小车控制', font=('Microsoft YaHei UI', 12, 'bold')).pack(anchor='w', pady=(0, 12))
        settings = ttk.Frame(side)
        settings.pack(fill='x')
        self.speed = tk.StringVar(value='100')
        self.distance = tk.StringVar(value='20')
        self.angle = tk.StringVar(value='90')
        self.move_inputs = []
        for row, (label, variable, end) in enumerate((('轮速', self.speed, 'mm/s'),
                                                     ('距离', self.distance, 'cm'),
                                                     ('转角', self.angle, '°'))):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Spinbox(settings, textvariable=variable, from_=1, to=400, width=9)
            entry.grid(row=row, column=1, padx=10, sticky='ew')
            ttk.Label(settings, text=end).grid(row=row, column=2, sticky='w')
            self.move_inputs.append(entry)
        settings.columnconfigure(1, weight=1)
        directions = ttk.Frame(side)
        directions.pack(fill='x', pady=14)
        for column in range(3):
            directions.columnconfigure(column, weight=1, uniform='direction')
        self.move_buttons = []
        for label, action, row, col in (('↑ 前进', 'forward', 0, 1), ('← 左转', 'left', 1, 0),
                                        ('右转 →', 'right', 1, 2), ('↓ 后退', 'backward', 2, 1)):
            button = ttk.Button(directions, text=label, command=lambda a=action: self.move(a), width=8)
            button.grid(row=row, column=col, sticky='ew', padx=2, pady=2)
            self.move_buttons.append(button)
        self.stop_button = tk.Button(side, text='■  停止', command=self.stop, background='#bb3845',
                                     foreground='white', activebackground='#9b2c36', activeforeground='white',
                                     font=('Microsoft YaHei UI', 13, 'bold'), relief='flat', pady=10)
        self.stop_button.pack(fill='x', pady=(0, 16))
        self.motion_state = tk.StringVar(value='未连接')
        ttk.Label(side, textvariable=self.motion_state, foreground='#157b69', wraplength=300).pack(anchor='w')
        telemetry = ttk.Frame(body)
        telemetry.grid(row=3, column=0, sticky='ew', pady=8)
        self.metrics = {}
        for column, label in enumerate(('轮速 L / R', '编码器 L / R', 'PWM L / R', '命令年龄', '故障码')):
            variable = tk.StringVar(value='--')
            self.metrics[label] = variable
            group = ttk.Frame(telemetry)
            group.grid(row=0, column=column, sticky='w', padx=(0, 16))
            telemetry.columnconfigure(column, weight=1, uniform='telemetry')
            ttk.Label(group, text=label, foreground='#58696c', font=('Microsoft YaHei UI', 9)).pack(anchor='w')
            ttk.Label(group, textvariable=variable, font=('Consolas', 11)).pack(anchor='w', pady=(3, 0))
        self.clear_button = ttk.Button(side, text='清除故障', command=self.clear_fault)
        self.clear_button.pack(anchor='e', pady=10)
        self.firmware = tk.StringVar(value='固件能力：待连接')
        ttk.Label(side, textvariable=self.firmware, foreground='#58696c', wraplength=300).pack(anchor='w')

        log_header = ttk.Frame(body)
        log_header.grid(row=4, column=0, sticky='ew', pady=(0, 4))
        ttk.Label(log_header, text='运行记录').pack(side='left')
        ttk.Button(log_header, text='清空', command=self.clear_log).pack(side='right')
        self.log = tk.Text(body, height=4, background='#fcfdfd', foreground='#334746', relief='flat',
                           font=('Microsoft YaHei UI', 9), wrap='word', padx=10, pady=6, state='disabled')
        self.log.grid(row=5, column=0, sticky='ew')
        self.controls()

    def mode_changed(self, event=None):
        self.address.set('192.168.0.2' if self.mode.get() in ('TCP', 'UDP') else
                         next((p.device for p in list_ports.comports()), 'COM4'))
        self.controls()

    def append_log(self, value):
        self.log.configure(state='normal')
        self.log.insert('end', time.strftime('%H:%M:%S') + '  ' + str(value) + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 500:
            self.log.delete('1.0', '100.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def controls(self):
        active = self.control is not None and self.control.is_alive()
        for widget in (self.mode_box, self.address_box, self.reverse_box):
            widget.configure(state='disabled' if active or self.closing else 'normal')
        if not active and not self.closing:
            self.mode_box.configure(state='readonly')
        self.tcp_entry.configure(state='normal' if not active and self.mode.get() in ('TCP', 'UDP') and not self.closing else 'disabled')
        self.connect_button.configure(state='disabled' if active or self.closing else 'normal')
        self.disconnect_button.configure(state='normal' if active and not self.closing else 'disabled')
        ready = self.connected and not self.busy and not self.closing
        for widget in self.move_buttons + self.move_inputs + [self.clear_button]:
            widget.configure(state='normal' if ready else 'disabled')
        running = self.video is not None and self.video.is_alive() or self.demo_video_running
        for entry in self.video_entries:
            entry.configure(state='disabled' if running or self.closing else 'normal')
        self.video_button.configure(text='关闭' if running else '接收', state='disabled' if self.closing else 'normal')
        self.capture_button.configure(state='normal' if self.last_frame and not self.closing else 'disabled')

    @property
    def demo_video_running(self):
        return getattr(self, '_demo_video', False)

    def connect(self):
        if self.control and self.control.is_alive():
            return
        try:
            port = int(self.tcp_port.get())
            if not 1 <= port <= 65535:
                raise ValueError('端口须为 1~65535')
            self.control = ControlWorker(self.mode.get(), self.address.get(), port,
                                         self.reverse.get(), self.events, self.demo)
            self.control.start()
            self.link_state.set('正在连接控制…')
            self.controls()
        except Exception as exc:
            messagebox.showerror('控制连接', str(exc), parent=self.root)

    def disconnect(self):
        self.connected = False
        if self.control:
            self.control.shutdown()
        self.link_state.set('正在停车并断开…')
        self.controls()

    def move(self, action):
        if not self.connected or self.busy or self.closing:
            return
        try:
            amount = float(self.distance.get() if action in ('forward', 'backward') else self.angle.get())
            move = Move(action, amount, int(self.speed.get()))
            move.targets()
            if move.speed > self.max_speed:
                raise ValueError(f'当前固件轮速最高 {self.max_speed} mm/s')
            if self.control.submit('move', move):
                self.busy = True
                self.motion_state.set('执行动作…')
                self.append_log(f'{action} / {amount:g} / {move.speed} mm/s')
                self.controls()
        except Exception as exc:
            messagebox.showerror('动作参数', str(exc), parent=self.root)

    def stop(self):
        if self.control and self.control.is_alive():
            self.control.stop()
            self.busy = True
            self.motion_state.set('正在停车…')
            self.controls()

    def key_stop(self, event):
        self.stop()
        return 'break'

    def clear_fault(self):
        if self.control and self.control.submit('clear_fault'):
            self.busy = True
            self.controls()

    def toggle_video(self):
        if self.demo_video_running or self.video and self.video.is_alive():
            self._demo_video = False
            if self.video:
                self.video.stop()
            self.camera_state.set('已关闭')
            self.last_frame = self.last_frame_at = None
            self.draw_frame()
            self.controls()
        else:
            self.start_video()

    def start_video(self):
        if self.demo:
            self._demo_video = True
            self.camera_state.set('模拟画面')
            self.controls()
            return
        try:
            bind = str(ipaddress.IPv4Address(self.bind_ip.get().strip()))
            source = str(ipaddress.IPv4Address(self.source_ip.get().strip()))
            port = int(self.video_port.get())
            if not 1 <= port <= 65535:
                raise ValueError('视频端口须为 1~65535')
            if self.video and self.video.is_alive():
                return
            self.video = VideoReceiver(bind, port, source, self.frames, self.events)
            self.video.start()
            self.camera_state.set('等待画面…')
            self.controls()
        except Exception as exc:
            messagebox.showerror('视频连接', str(exc), parent=self.root)

    def draw_frame(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 2 or height < 2:
            return
        self.canvas.delete('all')
        if self.last_frame is not None:
            image = self.last_frame.copy()
            image.thumbnail((width, height), Image.Resampling.BILINEAR)
            self.photo = ImageTk.PhotoImage(image)
            self.canvas.create_image(width//2, height//2, image=self.photo)
            if self.last_frame_at and time.monotonic() - self.last_frame_at > 1:
                self.canvas.create_rectangle(0, 0, width, 42, fill='#9b3540', outline='')
                self.canvas.create_text(width//2, 21, text='画面已过期', fill='white', font=('Microsoft YaHei UI', 12))
        else:
            self.canvas.create_text(width//2, height//2, text='等待摄像头画面', fill='#9aada9', font=('Microsoft YaHei UI', 15))

    def snapshot(self):
        if self.last_frame is None:
            return
        folder = ROOT / 'captures'
        try:
            folder.mkdir(exist_ok=True)
            path = folder / (time.strftime('%Y%m%d-%H%M%S') + f'-{time.time_ns() % 1000000000:09d}.png')
            self.last_frame.save(path)
            self.append_log(f'画面已保存：{path}')
        except OSError as exc:
            messagebox.showerror('保存画面', str(exc), parent=self.root)

    def process_event(self, kind, value):
        if kind == 'control_connected':
            self.connected = True
            caps, reverse = value
            self.max_speed = caps.max_speed if caps else 400
            self.reverse.set(reverse)
            self.firmware.set('A723 兼容 / 同步减速' if caps and caps.bridge_fixed else '旧固件 / 编码器行程控制')
            self.link_state.set(('模拟控制' if self.demo else f'{self.mode.get()} {self.address.get()}') + ' 已连接')
            self.append_log(f'控制已连接；右轮补偿：{"开" if reverse else "关"}')
        elif kind == 'control_disconnected':
            self.connected = self.busy = False
            self.link_state.set('控制已断开')
            self.motion_state.set('未连接')
            for variable in self.metrics.values():
                variable.set('--')
        elif kind == 'motion_idle':
            self.busy = self.control.busy if self.control else False
        elif kind == 'telemetry':
            self.motion_state.set(STATE_NAMES.get(value.state, f'状态 {value.state}'))
            self.metrics['轮速 L / R'].set(f'{value.left_speed} / {value.right_speed} mm/s')
            self.metrics['编码器 L / R'].set(f'{value.left_count} / {value.right_count}')
            self.metrics['PWM L / R'].set(f'{value.left_pwm} / {value.right_pwm}')
            self.metrics['命令年龄'].set(f'{value.command_age_ms} ms')
            self.metrics['故障码'].set(f'0x{value.faults:04X}')
        elif kind in ('log', 'error'):
            self.append_log(('错误：' if kind == 'error' else '') + str(value))
        elif kind == 'video_connected':
            self.append_log(f'视频 UDP 监听：{value}')
        elif kind == 'video_disconnected':
            self.camera_state.set('接收已停止')
        elif kind == 'video_stats':
            self.video_counts = value
        self.controls()

    def pump(self):
        for _ in range(80):
            try:
                self.process_event(*self.events.get_nowait())
            except queue.Empty:
                break
        now = time.monotonic()
        item = None
        if self.demo_video_running and not self.closing:
            self.demo_index += 1
            item = scene(self.demo_index), self.demo_index, now
        else:
            try:
                item = self.frames.get_nowait()
            except queue.Empty:
                pass
        if item:
            self.last_frame, self.frame_count, self.last_frame_at = item
            self.shown_frames += 1
            if now - self.fps_at >= 1:
                self.fps = self.shown_frames / (now - self.fps_at)
                self.fps_at, self.shown_frames = now, 0
            self.camera_state.set('模拟画面' if self.demo else '实时接收')
            counts = getattr(self, 'video_counts', (0, 0, 0))
            self.video_info.set(f'{self.last_frame.width} × {self.last_frame.height} / {self.fps:.1f} FPS'
                                f' / 帧 {self.frame_count} / 丢帧 {counts[1]} / 异常包 {counts[2]}')
            self.draw_frame()
            self.controls()
        elif self.last_frame_at and now - self.last_frame_at > 1:
            self.camera_state.set('画面已过期')
            self.draw_frame()
        if self.closing:
            alive = (self.control and self.control.is_alive()) or (self.video and self.video.is_alive())
            if not alive:
                self.root.destroy()
                return
        self.controls()
        self.root.after(40, self.pump)

    def close(self):
        self.closing = True
        self._demo_video = False
        if self.control:
            self.control.shutdown()
        if self.video:
            self.video.stop()
        self.link_state.set('正在停车并关闭…')
        self.controls()


def main():
    parser = argparse.ArgumentParser(description='EdgeMind camera and car controller')
    parser.add_argument('--demo', action='store_true', help='simulate video and motion without hardware')
    args = parser.parse_args()
    root = tk.Tk()
    CameraCarApp(root, demo=args.demo)
    root.mainloop()


if __name__ == '__main__':
    main()
