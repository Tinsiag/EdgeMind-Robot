"""A741 camera, lidar and manual motion console. No board I/O until Connect."""
from dataclasses import asdict
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
from calibration import Calibration, DEFAULT
from client import Client, HoldLease, CalibrationRejected
from telemetry import TelemetryReceiver
from video import VideoReceiver, FrameAssembler
from mapping import MappingWorker, map_display_image, map_display_point


class TrafficAssembler(FrameAssembler):
    def __init__(self):
        super().__init__()
        self.payload_bytes = 0

    def feed(self, data, now=None):
        self.payload_bytes += len(data)
        return super().feed(data, now)


def lidar_display_angle(raw_cdeg, calibration):
    clockwise=calibration.get("lidar_clockwise",True)
    offset=calibration.get("lidar_zero_offset_deg",0)
    return ((-raw_cdeg/100 if clockwise else raw_cdeg/100)+offset)%360


class App:
    def __init__(self, root, sensors_only=False):
        self.root = root
        self.sensors_only=sensors_only
        self.root.title("EdgeMind A741 · 传感器调试 / 禁止电机" if sensors_only else "EdgeMind A741")
        self.root.geometry("1280x850")
        self.root.minsize(1000, 720)
        self.calibration = Calibration.load()
        self.mapper = MappingWorker(self.calibration)
        self.mapping_generation = -1
        self.map_zoom=3.0
        self.map_center=(.5,.5)
        self.map_drag=None
        self.lidar_requested = False
        self.ui_alive = time.monotonic()
        self.config_path = DEFAULT
        self.client = self.telemetry = self.video = None
        self.image = self.photo = None
        self.fid = None
        self.frame_time = None
        self.frames = queue.Queue(maxsize=2)
        self.events = queue.Queue()
        self.jobs = queue.Queue(maxsize=1)
        self.cancel = threading.Event()
        self.held = HoldLease()
        self.shutdown = threading.Event()
        self.busy = False
        self.connected = False
        self.last_log = 0
        self.last_console_telemetry = 0
        self.log_filter = tk.StringVar(value="ALL")
        self.started = time.monotonic()
        self.session_dir = Path(__file__).resolve().parents[1] / ".local/logs" / datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.logfile = (self.session_dir / "session.jsonl").open("a", encoding="utf-8")
        self.make_ui()
        self.thread = threading.Thread(target=self.worker, daemon=True, name="A741-control")
        self.thread.start()
        root.bind_all("<ButtonRelease-1>", lambda _: self.held.clear(), add="+")
        root.bind("<FocusOut>", lambda _: root.after(20, self.focus_check), add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self.refresh)

    def make_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        bar = ttk.Frame(self.root, padding=8)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="FPGA IP").pack(side="left")
        self.ip = tk.StringVar(value="192.168.0.2")
        ttk.Entry(bar, textvariable=self.ip, width=16).pack(side="left", padx=6)
        self.connect_button = ttk.Button(bar, text="连接", command=self.connect)
        self.connect_button.pack(side="left")
        ttk.Button(bar, text="断开", command=lambda: self.submit("disconnect")).pack(side="left", padx=6)
        ttk.Button(bar, text="标定参数", command=self.edit_config).pack(side="left")
        ttk.Button(bar, text="截图", command=self.screenshot).pack(side="left", padx=6)
        tk.Button(bar, text="停止 / 取消", bg="#b91c1c", fg="white", command=self.stop, padx=16).pack(side="right")
        self.connection_text = tk.StringVar(value="未连接")
        ttk.Label(bar, textvariable=self.connection_text).pack(side="right", padx=12)
        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.grid(row=1, column=0, sticky="nsew", padx=8)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes, width=360)
        panes.add(left, weight=3);panes.add(right, weight=1)
        sensor_status=ttk.Frame(right)
        sensor_status.pack(side="bottom",fill="x")
        left.rowconfigure(0, weight=1);left.columnconfigure(0, weight=1)
        self.camera = tk.Canvas(left, bg="#11181b", highlightthickness=0)
        self.camera.grid(row=0, column=0, sticky="nsew")
        self.video_text = tk.StringVar(value="摄像头：等待数据")
        ttk.Label(left, textvariable=self.video_text).grid(row=1, column=0, sticky="w", pady=4)
        self.sensor_tabs = ttk.Notebook(right)
        self.sensor_tabs.pack(fill="both", expand=True)
        radar_page = ttk.Frame(self.sensor_tabs);map_page = ttk.Frame(self.sensor_tabs)
        self.sensor_tabs.add(radar_page,text="雷达扫描");self.sensor_tabs.add(map_page,text="2D地图")
        radar_bar=ttk.Frame(radar_page);radar_bar.pack(fill="x")
        self.lidar_start=ttk.Button(radar_bar,text="启动雷达",command=lambda:self.submit("lidar",self.calibration.data.get("lidar_duty_permille",400)))
        self.lidar_start.pack(side="left")
        ttk.Button(radar_bar,text="停止雷达",command=self.stop).pack(side="left",padx=4)
        self.radar = tk.Canvas(radar_page, width=340, height=300, bg="#101d18", highlightthickness=0)
        self.radar.pack(fill="both", expand=True)
        map_bar=ttk.Frame(map_page);map_bar.pack(fill="x")
        ttk.Button(map_bar,text="新建地图",command=self.start_mapping).pack(side="left")
        ttk.Button(map_bar,text="暂停",command=lambda:self.mapper.command("pause")).pack(side="left",padx=3)
        ttk.Button(map_bar,text="保存",command=self.save_map).pack(side="left")
        ttk.Button(map_bar,text="导出返程路线",command=self.save_reverse_route).pack(side="left",padx=3)
        ttk.Button(map_bar,text="清空",command=lambda:self.mapper.command("clear")).pack(side="left",padx=3)
        ttk.Button(map_bar,text="+",width=3,command=lambda:self.zoom_map(1.25)).pack(side="left")
        ttk.Button(map_bar,text="-",width=3,command=lambda:self.zoom_map(.8)).pack(side="left")
        self.map_canvas=tk.Canvas(map_page,width=340,height=300,bg="#68747b",highlightthickness=0)
        self.map_canvas.pack(fill="both",expand=True)
        self.map_canvas.bind("<MouseWheel>",lambda e:self.zoom_map(1.25 if e.delta>0 else .8))
        self.map_canvas.bind("<ButtonPress-1>",lambda e:setattr(self,"map_drag",(e.x,e.y)))
        self.map_canvas.bind("<B1-Motion>",self.pan_map)
        self.mapping_text=tk.StringVar(value="未建图")
        ttk.Label(map_page,textvariable=self.mapping_text,wraplength=330).pack(fill="x")
        self.sensors_text = tk.StringVar(value="IMU：无效\nToF：无效\n雷达：无效")
        ttk.Label(sensor_status, textvariable=self.sensors_text, justify="left").pack(fill="x", pady=8)
        self.motion_text = tk.StringVar(value="运动：未连接")
        ttk.Label(sensor_status, textvariable=self.motion_text, justify="left").pack(fill="x")
        self.diag_text = tk.StringVar(value="UDP：等待")
        self.diagnostic_label=ttk.Label(sensor_status, textvariable=self.diag_text, justify="left")
        self.diagnostic_label.pack(fill="x", pady=8)
        control = ttk.Frame(self.root, padding=8)
        control.grid(row=2, column=0, sticky="ew")
        self.speed = tk.IntVar(value=100)
        self.angular = tk.DoubleVar(value=30)
        self.distance = tk.DoubleVar(value=20)
        self.degrees = tk.DoubleVar(value=90)
        for col, (label, var, start, end) in enumerate([
                ("轮速 mm/s", self.speed, 40, self.calibration.data["max_speed_mm_s"]),
                ("距离 cm", self.distance, 2, 1000), ("转角 °", self.degrees, 1, 360)]):
            ttk.Label(control, text=label).grid(row=0, column=col*2, sticky="w", padx=3)
            ttk.Spinbox(control, textvariable=var, from_=start, to=end, width=9).grid(row=0, column=col*2+1, padx=5)
        manual = ttk.Frame(control)
        manual.grid(row=1, column=0, columnspan=8, sticky="w", pady=8)
        for label, direction, turn, row, col in [("按住前进", 1, 0, 0, 1),
                ("按住原地左转", 0, 1, 1, 0), ("按住原地右转", 0, -1, 1, 2),
                ("按住后退", -1, 0, 2, 1)]:
            b = ttk.Button(manual, text=label, width=12)
            if self.sensors_only:b.configure(state="disabled")
            b.grid(row=row,column=col,padx=3,pady=3)
            b.bind("<ButtonPress-1>", lambda _e,d=direction,t=turn: self.hold(d,t))
            b.bind("<ButtonRelease-1>", lambda _e: self.stop())
        ttk.Button(manual,text="停止 / 取消",command=self.stop).grid(row=1,column=1,padx=3,pady=3)
        ttk.Button(manual,text="定距前进",width=12,
                   state="disabled" if self.sensors_only else "normal",
                   command=lambda:self.motion_job("distance",1)).grid(row=0,column=3,padx=8,pady=3)
        ttk.Button(manual,text="定距后退",width=12,
                   state="disabled" if self.sensors_only else "normal",
                   command=lambda:self.motion_job("distance",-1)).grid(row=2,column=3,padx=8,pady=3)
        service=ttk.Frame(control);service.grid(row=1,column=6,columnspan=2,sticky="e")
        ttk.Button(service, text="静止校准", command=lambda: self.submit("calibrate")).pack(pady=3)
        ttk.Button(service, text="IMU诊断", command=lambda: self.submit("imu_diagnostics")).pack(pady=3)
        ttk.Button(service, text="清除故障", command=lambda: self.submit("clear")).pack(pady=3)
        log_bar=ttk.Frame(self.root);log_bar.grid(row=3,column=0,sticky="ew",padx=8,pady=(8,0))
        ttk.Label(log_bar,text="日志级别").pack(side="left")
        ttk.OptionMenu(log_bar,self.log_filter,"ALL","ALL","INFO","DEBUG","WARNING","ERROR").pack(side="left",padx=5)
        self.log_view = tk.Text(self.root, height=7, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_view.grid(row=4, column=0, sticky="ew", padx=8, pady=8)

    def log(self, kind, value, level=None):
        if level is None:
            level = {"error":"ERROR", "warning":"WARNING", "telemetry":"DEBUG",
                     "telemetry_summary_error":"WARNING", "connection_diagnostics":"WARNING"}.get(kind, "INFO")
        entry = {"utc": datetime.now(timezone.utc).isoformat(), "host_monotonic": time.monotonic(),
                 "level": level, "kind": kind, "value": value, "config_revision": self.calibration.data["revision"],
                 "config_sha256": self.calibration.digest, "video_frame": self.fid}
        self.logfile.write(json.dumps(entry, ensure_ascii=False, default=str)+"\n")
        self.logfile.flush()
        selected = self.log_filter.get() if hasattr(self, "log_filter") else "ALL"
        if kind != "telemetry" and (selected == "ALL" or selected == level):
            self.log_view.configure(state="normal")
            self.log_view.insert("end", f"{datetime.now():%H:%M:%S} [{level}] {value}\n")
            if int(self.log_view.index("end-1c").split(".")[0]) > 300:
                self.log_view.delete("1.0", "20.0")
            self.log_view.see("end");self.log_view.configure(state="disabled")

    def log_telemetry_summary(self, snap, client, telemetry, video):
        """Show a compact live line while retaining the full JSON telemetry record."""
        now = time.monotonic()
        if now-self.last_console_telemetry < .25:
            return
        self.last_console_telemetry = now
        d = client.diag if client else None
        net = snap.network_diagnostics()
        left_pwm = getattr(snap, "left_pwm", None)
        right_pwm = getattr(snap, "right_pwm", None)
        pwm_text = "NA/NA" if left_pwm is None or right_pwm is None else f"{left_pwm}/{right_pwm}"
        line = (
            f"TEL ms={snap.ms} seq={snap.seq} state={snap.state} fault=0x{snap.faults:04x} "
            f"target={snap.left_target}/{snap.right_target} "
            f"speed={snap.left_speed}/{snap.right_speed} "
            f"count={snap.left_count}/{snap.right_count} "
            f"pwm={pwm_text} "
            f"yaw={snap.yaw_raw} gyro={snap.gyro_raw} "
            f"imu={'OK' if snap.flags & 4 else 'INVALID'} "
            f"net={net.get('bridge_state','NA')} badfcs={net.get('rx_bad_fcs_saturated15','NA')}"
        )
        if d:
            line += f" req={d.request_id} reply={d.replies}/{d.requests} timeout={d.timeouts} rtt={d.rtt_ms:.1f}ms"
        if telemetry:
            td=telemetry.diagnostics()
            line += f" lidar_gap={td.get('scan_gaps',0)} lidar_bad={td.get('host_bad_packets',0)}"
        if video:
            line += f" video={video.assembler.completed}/{video.assembler.dropped}"
        self.log_view.configure(state="normal")
        self.log_view.insert("end", f"{datetime.now():%H:%M:%S.%f}"[:-3]+" "+line+"\n")
        if int(self.log_view.index("end-1c").split(".")[0]) > 300:
            self.log_view.delete("1.0", "20.0")
        self.log_view.see("end");self.log_view.configure(state="disabled")

    def submit(self, kind, *args):
        if getattr(self,"sensors_only",False) and kind in ("drive","distance","rotate"):
            self.log("error","传感器调试模式禁止电机指令")
            return False
        if self.busy or self.shutdown.is_set():
            if not self.shutdown.is_set():self.log("message", "控制任务进行中，请先停止 / 取消后再操作")
            return False
        if kind not in ("connect", "disconnect") and not self.connected:
            return False
        self.cancel.clear()
        self.busy = True
        self.jobs.put_nowait((kind, args))
        return True

    def connect(self):
        if self.busy or self.connected:
            return
        if self.submit("connect", self.ip.get().strip()):
            self.connect_button.configure(state="disabled")
            self.connection_text.set("正在连接，请等待")

    def motion_job(self, kind, direction=1):
        try:
            value = direction*abs(self.distance.get()*10 if kind == "distance" else self.degrees.get())
            speed = self.motion_speed()
            if kind == "distance" and (not math.isfinite(value) or not 20 <= abs(value) <= 10000):
                raise ValueError("距离须为 ±20～10000 mm")
            if kind == "rotate" and (not math.isfinite(value) or not 1 <= abs(value) <= 360):
                raise ValueError("旋转角度须为 ±1～360°")
            self.submit(kind, value, speed)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("参数", str(exc))

    def motion_speed(self):
        speed = self.speed.get()
        maximum = self.calibration.data["max_speed_mm_s"]
        if not 40 <= speed <= maximum:
            raise ValueError(f"速度须为 40～{maximum} mm/s；当前输入 {speed} mm/s")
        return speed

    def hold(self, direction, turn):
        if self.busy or not self.connected:
            return
        try:
            speed, angular = direction*self.motion_speed(), turn*self.angular.get()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("参数", str(exc))
            return
        self.held.set()
        self.submit("drive", speed, angular)

    def focus_check(self):
        if self.root.focus_get() is None:
            self.held.clear()
            if self.lidar_requested:
                self.stop()

    def stop(self):
        self.lidar_requested=False
        self.held.clear();self.cancel.set()
        if not self.busy and self.connected:
            self.submit("stop")

    def cleanup(self):
        self.lidar_requested=False
        self.mapper.command("pause","控制连接断开，地图保留")
        if self.client:
            try:
                self.client.stop()
            except TimeoutError as exc:
                self.events.put(("warning", f"UDP短时超时，保持连接：{exc}"))
            except Exception as exc:
                self.events.put(("message", f"UDP 停止未确认：{exc}；FPGA 命令超时保护仍须实测"))
            self.client.close()
        if self.telemetry:
            self.telemetry.close()
        if self.video:
            self.video.stop();self.video.join(timeout=.5)
        self.client = self.telemetry = self.video = None
        self.events.put(("disconnected", None))

    def worker(self):
        while not self.shutdown.is_set():
            try:
                kind, args = self.jobs.get(timeout=.1)
            except queue.Empty:
                if self.client and getattr(self,"lidar_requested",False):
                    try:
                        if time.monotonic()-self.ui_alive<.3:
                            self.client.heartbeat()
                        else:
                            self.client.lidar(0);self.lidar_requested=False
                    except TimeoutError as exc:
                        self.events.put(("warning", f"后台心跳/雷达请求短时超时，保持连接：{exc}"))
                    except Exception as exc:
                        self.events.put(("error",str(exc)));self.cleanup()
                continue
            try:
                if kind == "connect":
                    self.cleanup()
                    self.client = Client(args[0])
                    self.client.sensors_only=getattr(self,"sensors_only",False)
                    self.telemetry = TelemetryReceiver(args[0])
                    status = self.client.connect(self.calibration)
                    if self.cancel.is_set():
                        raise RuntimeError("连接已取消")
                    self.video = VideoReceiver("0.0.0.0", 6102, args[0], self.frames, self.events)
                    self.video.assembler = TrafficAssembler()
                    self.video.start()
                    self.events.put(("connected", asdict(status)))
                    if self.client.imu_test:
                        self.events.put(("message", "IMU 测试模式：电机硬件锁定；ToF/雷达未启用；用IMU诊断确认实际身份"))
                    elif self.client.motion_lidar:
                        self.events.put(("message","运动+LD06模式：雷达CTL H20 / DATA H14；未安装ToF，无自动前向保护"))
                    if self.client.imu_test or self.client.motion_lidar:
                        self.events.put(("message", "连接后自动IMU诊断与静止校准开始，请保持水平静止；不会自动启动电机"))
                        result = self.client.calibrate(self.cancel)
                        self.events.put(("message", {"automatic_calibration": result}))
                elif kind == "disconnect":
                    self.cleanup()
                elif kind == "stop":
                    self.events.put(("message", asdict(self.client.stop())))
                elif kind == "calibrate":
                    self.lidar_requested=False
                    self.events.put(("message", self.client.calibrate(self.cancel)))
                elif kind == "imu_diagnostics":
                    self.events.put(("message", self.client.imu_diagnostics()))
                elif kind == "lidar":
                    result=self.client.lidar(args[0]);self.lidar_requested=args[0]!=0
                    self.events.put(("message",result))
                elif kind == "clear":
                    self.lidar_requested=False
                    try:
                        self.client.stop()
                        self.client.command(0x21)
                        status = self.client.status()
                    except TimeoutError as exc:
                        raise CalibrationRejected(f"清故障结果未确认（{exc}）；连接保持，请先读取状态，不要连续重试") from exc
                    if status.faults:
                        raise CalibrationRejected(f"FPGA 故障仍未清除：0x{status.faults:04x}；检查编码器反馈及车轮状态")
                    self.events.put(("message", "FPGA 故障已清除；下一次运动仍须人工启动"))
                else:
                    self.events.put(("message", {"motion_start": kind, "parameters": args}))
                    if kind == "drive":
                        result = self.client.drive(self.calibration, *args, self.held, self.cancel)
                    else:
                        result = getattr(self.client, kind)(self.calibration, *args, self.cancel)
                    self.events.put(("message", result))
                    if self.cancel.is_set():self.lidar_requested=False
            except CalibrationRejected as exc:
                self.events.put(("error", str(exc)))
            except TimeoutError as exc:
                # UDP loss is recoverable; FPGA command TTL/STOP remains the safety boundary.
                if self.client:
                    try:
                        self.client.stop()
                    except Exception as stop_exc:
                        self.events.put(("warning", f"超时后的STOP未确认：{stop_exc}"))
                self.events.put(("warning", f"UDP请求短时超时，连接保持：{exc}"))
            except Exception as exc:
                if self.telemetry:
                    snapshot,_=self.telemetry.read()
                    self.events.put(("connection_diagnostics",{
                        "control":asdict(self.client.diag) if self.client else None,
                        "fpga_ms":snapshot.ms if snapshot else None,
                        "fpga_network":snapshot.network_diagnostics() if snapshot else None,
                        "flags":hex(snapshot.flags) if snapshot else None}))
                self.events.put(("error", str(exc)))
                self.cleanup()
            finally:
                if self.cancel.is_set() and self.client:
                    self.lidar_requested=False
                    try:self.client.stop()
                    except Exception as exc:
                        self.events.put(("error",str(exc)));self.cleanup()
                self.events.put(("idle", None))
        self.cleanup()

    def refresh(self):
        if self.shutdown.is_set():
            return
        self.held.renew()
        self.ui_alive=time.monotonic()
        telemetry, client, video = self.telemetry, self.client, self.video
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "idle":
                self.busy = False
            elif kind == "connected":
                self.connected = True;self.connection_text.set("IMU测试 · 电机锁定" if client and client.imu_test else "运动+LD06 · 无ToF" if client and client.motion_lidar else "A741 · UDP 已连接")
                self.log(kind, value)
            elif kind == "disconnected":
                self.connected = False;self.connection_text.set("未连接")
            elif kind == "video_stats":
                self.video_text.set(f"视频完成 {value[0]}  丢帧 {value[1]}  坏包 {value[2]}")
            elif kind in ("error", "warning", "message", "connection_diagnostics"):
                self.log(kind, value)
        changed = False
        while True:
            try:
                self.image, self.fid, self.frame_time = self.frames.get_nowait();changed = True
            except queue.Empty:
                break
        cw, ch = self.camera.winfo_width(), self.camera.winfo_height()
        if self.image is not None and (changed or getattr(self, "canvas_size", None) != (cw, ch)):
            self.canvas_size = (cw, ch)
            scale = min(max(1, cw)/self.image.width, max(1, ch)/self.image.height)
            display = self.image.resize((max(1, round(self.image.width*scale)), max(1, round(self.image.height*scale))), resample=0)
            self.photo = ImageTk.PhotoImage(display)
            self.camera.delete("all");self.camera.create_image(cw/2, ch/2, image=self.photo)
        self.camera.delete("stale")
        if self.frame_time is None or time.monotonic()-self.frame_time > .5:
            self.camera.create_text(12, 12, text="视频无效 / 过期", fill="white", anchor="nw", tags="stale")
        snap, points = telemetry.read() if telemetry and self.connected else (None, ())
        if telemetry and self.connected:
            for sample in telemetry.mapping_samples():
                self.mapper.feed(sample)
        raw,pose,trajectory,generation,status,active=self.mapper.snapshot()
        self.mapping_text.set(status)
        map_event=(active,status if not status.startswith("建图 ") else "正在建图")
        if getattr(self,"last_mapping_event",None)!=map_event:
            self.last_mapping_event=map_event
            self.log("mapping_state",{"active":active,"status":status,"frames":generation})
        self.draw_map(raw,pose,trajectory,generation)
        self.draw_radar(points)
        if snap:
            label = lambda bit, text: text if snap.flags & (1 << bit) else "无效 / 过期"
            heading_text = label(0, f'{snap.yaw_raw*180/32768:.2f}°') if snap.flags & 16 else "未校准"
            tof_text = "未接入，无前向停车保护" if client and client.motion_lidar else label(2, f'{snap.tof_mm} mm')
            self.sensors_text.set(f"IMU 相对航向：{heading_text}\n"
                                  f"角速度：{label(1, f'{snap.gyro_raw*2000/32768:.2f}°/s')}\n"
                                  f"ToF：{tof_text}\n雷达：{'有效' if points else '无效 / 过期'}\n"
                                  f"IMU 样本 {snap.imu_seq} · 错误 {snap.imu_errors}\n"
                                  f"雷达包 {snap.lidar_seq} · 累计校验/串口错 {snap.lidar_errors}\n"
                                  f"FPGA 时间：{snap.ms} ms · 配置 {snap.revision}")
            self.motion_text.set(f"模式 {snap.state}  故障 0x{snap.faults:04x}\n"
                                 f"目标 L/R：{snap.left_target} / {snap.right_target} mm/s\n"
                                 f"实测 L/R：{snap.left_speed} / {snap.right_speed} mm/s\n"
                                 f"DDR：{'就绪' if snap.flags & 256 else '未就绪'}")
            if time.monotonic()-self.last_log > .1:
                traffic = {"sensors": asdict(snap), "communication": asdict(client.diag) if client else None,
                           "fpga_network":snap.network_diagnostics(),
                           "lidar_receiver":telemetry.diagnostics() if telemetry else None,
                           "video_payload_bytes": video.assembler.payload_bytes if video else 0,
                           "video_completed": video.assembler.completed if video else 0,
                           "video_dropped": video.assembler.dropped if video else 0}
                self.log("telemetry", traffic);self.last_log = time.monotonic()
            try:
                self.log_telemetry_summary(snap, client, telemetry, video)
            except Exception as exc:
                # A logging/display field must never stop Tk's periodic refresh.
                self.logfile.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
                    "kind": "telemetry_summary_error", "value": repr(exc)}, ensure_ascii=False)+"\n")
                self.logfile.flush()
        else:
            self.sensors_text.set("IMU：无效 / 过期\nToF：无效 / 过期\n雷达：无效 / 过期")
            self.motion_text.set("运动遥测：无效 / 过期")
        if client:
            d = client.diag
            receiver=telemetry.diagnostics() if telemetry else {}
            bandwidth = (telemetry.bytes if telemetry else 0) / max(1, time.monotonic()-self.started)
            video_bandwidth = (video.assembler.payload_bytes if video else 0) / max(1, time.monotonic()-self.started)
            self.diag_text.set(f"请求 {d.request_id} · RTT {d.rtt_ms:.1f} ms\n"
                               f"超时 {d.timeouts} · 重试 {d.retries} · 丢弃 {d.discarded}\n"
                               f"PC雷达校验错 {receiver.get('host_bad_packets',0)} · 缺包/断点 {receiver.get('scan_gaps',0)}\n"
                               f"遥测 {bandwidth/1024:.1f} KiB/s · 视频 {video_bandwidth/1048576:.2f} MiB/s")
        self.lidar_start.configure(state="normal" if self.connected and client and client.motion_lidar and not self.busy else "disabled")
        self.connect_button.configure(state="disabled" if self.connected or self.busy else "normal")
        self.root.after(50, self.refresh)

    def draw_radar(self, points):
        c = self.radar;c.delete("all")
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        cx, cy, radius = w/2, h/2, min(w, h)*.44
        for ring in (1/3, 2/3, 1):
            r = radius*ring;c.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#385648")
        c.create_line(cx-radius, cy, cx+radius, cy, fill="#385648")
        c.create_line(cx, cy-radius, cx, cy+radius, fill="#385648")
        c.create_text(cx, 10, text="前方 · 量程 3 m", fill="#d2e9d9", anchor="n")
        for angle, distance, confidence in points:
            if confidence < 10 or not 0 < distance <= 3000:
                continue
            degrees=lidar_display_angle(angle,self.calibration.data)
            rad = math.radians(degrees);r = radius*distance/3000
            x, y = cx-r*math.sin(rad), cy-r*math.cos(rad)
            c.create_rectangle(x-1, y-1, x+1, y+1, fill="#7ce3ad", outline="")
        if not points:
            c.create_text(cx, cy, text="无效 / 过期", fill="#d2e9d9")

    def start_mapping(self):
        if not self.connected or not self.client or not self.client.motion_lidar:
            messagebox.showinfo("建图","请先连接运动+LD06固件，启动雷达并完成IMU静止校准")
            return
        self.mapper.start(self.calibration)
        self.mapping_generation=-1
        self.map_draw_key=None
        self.map_zoom=3.0;self.map_center=(.5,.5)

    def zoom_map(self, factor):
        self.map_zoom=max(1.0,min(8.0,self.map_zoom*factor))

    def pan_map(self, event):
        if self.map_drag:
            size=max(1,min(self.map_canvas.winfo_width(),self.map_canvas.winfo_height())*self.map_zoom)
            dx,dy=event.x-self.map_drag[0],event.y-self.map_drag[1]
            self.map_center=(max(0,min(1,self.map_center[0]-dx/size)),max(0,min(1,self.map_center[1]-dy/size)))
        self.map_drag=(event.x,event.y)

    def save_map(self):
        path=filedialog.asksaveasfilename(defaultextension=".png",initialfile="map.png",filetypes=[("地图PNG","*.png")])
        if path:
            try:self.log("map",self.mapper.save(path))
            except Exception as exc:messagebox.showerror("保存地图",str(exc))

    def save_reverse_route(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",initialfile="reverse-route.json",filetypes=[("返程路线JSON","*.json")])
        if path:
            try:self.log("map",self.mapper.save_reverse_route(path))
            except Exception as exc:messagebox.showerror("导出返程路线",str(exc))

    def draw_map(self,raw,pose,trajectory,generation):
        c=self.map_canvas
        w,h=max(1,c.winfo_width()),max(1,c.winfo_height())
        key=(generation,w,h,raw is None,self.map_zoom,self.map_center)
        if getattr(self,"map_draw_key",None)==key:return
        self.map_draw_key=key;c.delete("all")
        if raw is None:
            c.create_text(w/2,h/2,text="未建图",fill="white");return
        size=max(1,round(min(w,h)*self.map_zoom));ox=w/2-self.map_center[0]*size;oy=h/2-self.map_center[1]*size
        image=map_display_image(raw)
        self.map_photo=ImageTk.PhotoImage(image.resize((size,size),Image.Resampling.NEAREST))
        c.create_image(ox,oy,anchor="nw",image=self.map_photo)
        def xy(p):
            u,v=map_display_point(p)
            return ox+u*size,oy+v*size
        for n in range(1,10):
            q=n*size/10;c.create_line(ox+q,oy,ox+q,oy+size,fill="#bac0c5");c.create_line(ox,oy+q,ox+size,oy+q,fill="#bac0c5")
        path=[value for p in trajectory for value in xy(p)]
        if len(path)>3:c.create_line(*path,fill="#247caf",width=2)
        if pose:
            x,y=xy(pose);a=math.radians(pose[2]);c.create_oval(x-4,y-4,x+4,y+4,fill="#d54336",outline="")
            c.create_line(x,y,x-12*math.sin(a),y-12*math.cos(a),fill="#d54336",arrow="last",width=2)
        length=size*2/30
        c.create_rectangle(8,h-36,20+length,h-5,fill="white",outline="#939ca1")
        c.create_line(14,h-13,14+length,h-13,fill="#20282c",width=2)
        c.create_text(14+length/2,h-25,text="2 m",fill="#20282c")

    def edit_config(self):
        if self.connected or self.busy:
            messagebox.showinfo("标定参数", "请先停止并断开控制连接")
            return
        dialog = tk.Toplevel(self.root);dialog.title("A741 标定配置")
        text = tk.Text(dialog, width=90, height=27)
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", json.dumps(self.calibration.data, ensure_ascii=False, indent=2))
        def save():
            try:
                config = Calibration(json.loads(text.get("1.0", "end")))
                config.values(False)
                if config.data["revision"] <= self.calibration.data["revision"] and config.data != self.calibration.data:
                    raise ValueError("修改参数后请递增 revision")
                path = filedialog.asksaveasfilename(parent=dialog, defaultextension=".json", initialfile="calibration.json")
                if path:
                    config.save(path);self.calibration = config;self.config_path = Path(path)
                    self.log("config", config.data);dialog.destroy()
            except Exception as exc:
                messagebox.showerror("配置", str(exc), parent=dialog)
        def load():
            path = filedialog.askopenfilename(parent=dialog, filetypes=[("JSON", "*.json")])
            if path:
                try:
                    cfg = Calibration.load(path)
                    text.delete("1.0", "end");text.insert("1.0", json.dumps(cfg.data, ensure_ascii=False, indent=2))
                except Exception as exc:
                    messagebox.showerror("配置", str(exc), parent=dialog)
        ttk.Button(dialog, text="载入", command=load).pack(side="left", padx=8, pady=8)
        ttk.Button(dialog, text="保存并采用", command=save).pack(side="right", padx=8, pady=8)

    def screenshot(self):
        if self.image is None:
            return
        name = self.session_dir / f"frame-{self.fid}-{time.time_ns()}"
        self.image.save(name.with_suffix(".png"))
        snap, points = self.telemetry.read() if self.telemetry else (None, ())
        meta = {"video_frame": self.fid, "host_receive_monotonic": self.frame_time,
                "snapshot": asdict(snap) if snap else None, "lidar_points": points,
                "config": self.calibration.data, "config_sha256": self.calibration.digest,
                "synchronization": "latest received snapshot; not a camera exposure timestamp"}
        name.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log("screenshot", str(name))

    def close(self):
        self.held.clear();self.cancel.set();self.shutdown.set()
        self.connection_text.set("正在停止并断开")
        def finish():
            if self.thread.is_alive():
                self.root.after(50, finish)
            else:
                self.mapper.close();self.logfile.close();self.root.destroy()
        finish()


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--sensors-only",action="store_true",help="disable all motor commands for VM-off sensor tests")
    args=parser.parse_args()
    root = tk.Tk()
    app = App(root,sensors_only=args.sensors_only)
    root.mainloop()
