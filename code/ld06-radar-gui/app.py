"""Chinese LD06 radar viewer. Run: python app.py [--demo] [--port COM7]."""
import argparse
import csv
from datetime import datetime
import math
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from demo import Demo
from protocol import Parser
from receiver import Receiver
from scan import Scan, xy
from view import RADII, contours, directional_distances, distance_text, fitted_radius

BG = "#f6f8fb"
PANEL = "#ffffff"
PLOT = "#ffffff"
TEXT = "#243247"
MUTED = "#718096"
ACCENT = "#2563eb"
GRID = "#e2e8f0"
AMBER = "#b45309"


class RadarApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("LD06 激光雷达 · Radar Viewer")
        root.geometry("1100x800")
        root.minsize(960, 680)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.parser = Parser()
        self.scan = Scan()
        self.worker = None
        self.mode = "idle"
        self.demo_source = None
        self.demo_next = 0.0
        self.started = time.monotonic()
        self.byte_count = 0
        self.rate_bytes = 0
        self.rate_time = self.started
        self.rate = 0.0
        self.paused = False
        self.frozen = ()
        self.frozen_angle = 0.0
        self.frozen_at = 0.0
        self.visible = ()
        self.view_rotation = 0.0
        self.grid_signature = None
        self.closed = False
        self.port = tk.StringVar()
        self.radius = tk.StringVar(value="自动")
        self.confidence = tk.StringVar(value="10")
        self.rotation = tk.StringVar(value="0")
        self.retention = tk.StringVar(value="0.6")
        self.show_contours = tk.BooleanVar(value=True)
        self.display_radius = 1.0
        self.range_changed_at = 0.0
        self.last_dropped = 0
        self.status = tk.StringVar(value="未连接")
        self.detail = tk.StringVar(value="连接 PWLINK2 后刷新串口，或点击模拟预览。")
        self.cursor_text = tk.StringVar(value="蓝线：连续回波轮廓　浅蓝：测距扇区　橙点：最近回波")
        self.stats = {key: tk.StringVar(value="—") for key in
                      ("hz", "points", "near", "frames", "crc", "bytes", "rate", "drop")}
        self._styles()
        self._layout()
        self.refresh_ports()
        self.timer = root.after(33, self.tick)

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL, background="#eef2f7",
                        foreground=TEXT, arrowcolor=ACCENT, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)],
                  foreground=[("readonly", TEXT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))

    def label(self, parent, text=None, *, variable=None, color=TEXT, size=10, bold=False, **kw):
        return tk.Label(parent, text=text, textvariable=variable, bg=parent.cget("bg"),
                        fg=color, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"), **kw)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command,
                         bg=ACCENT if primary else "#edf1f6", fg=PANEL if primary else TEXT,
                         activebackground="#1d4ed8" if primary else "#e2e8f0",
                         activeforeground=PANEL if primary else TEXT,
                         disabledforeground="#a0aec0", relief="flat", bd=0,
                         padx=12, pady=6, cursor="hand2", takefocus=True)

    def _layout(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 14))
        self.label(header, "LD06 激光雷达", size=17, bold=True).pack(side="left")
        self.badge = self.label(header, "●  未连接", color=MUTED, size=10)
        self.badge.pack(side="right")
        toolbar = tk.Frame(self.root, bg=BG)
        toolbar.pack(fill="x", padx=24, pady=(0, 10))
        self.label(toolbar, "串口", color=MUTED).pack(side="left", padx=(0, 8))
        self.port_box = ttk.Combobox(toolbar, textvariable=self.port, width=10)
        self.port_box.pack(side="left")
        self.refresh_button = self.button(toolbar, "刷新", self.refresh_ports)
        self.refresh_button.pack(side="left", padx=6)
        self.connect_button = self.button(toolbar, "连接雷达", self.toggle_connection, True)
        self.connect_button.pack(side="left")
        self.demo_button = self.button(toolbar, "模拟预览", self.toggle_demo)
        self.demo_button.pack(side="left", padx=6)
        self.label(toolbar, "230400 · 8N1", color=MUTED, size=9).pack(side="left", padx=8)
        self.button(toolbar, "导出 CSV", self.export).pack(side="right")
        self.button(toolbar, "清空", self.clear).pack(side="right", padx=6)
        self.pause_button = self.button(toolbar, "暂停画面", self.toggle_pause)
        self.pause_button.pack(side="right")

        settings = tk.Frame(self.root, bg=BG)
        settings.pack(fill="x", padx=24, pady=(0, 12))
        for title, variable, values in (
            ("半径 / m", self.radius, ("自动", "0.2", "0.3", "0.5", "1", "2", "3", "6", "8", "12")),
            ("最低强度", self.confidence, ("0", "10", "30", "50", "100", "150")),
            ("旋转 / °", self.rotation, ("0", "90", "180", "270")),
            ("保留 / s", self.retention, ("0.2", "0.6", "1.0", "2.0")),
        ):
            row = tk.Frame(settings, bg=BG)
            row.pack(side="left", padx=(0, 20))
            self.label(row, title, color=MUTED, size=9).pack(side="left", padx=(0, 7))
            ttk.Combobox(row, textvariable=variable, values=values, width=5,
                         state="readonly").pack(side="left")
        tk.Checkbutton(settings, text="障碍轮廓", variable=self.show_contours,
                       bg=BG, fg=TEXT, activebackground=BG, selectcolor=PANEL,
                       bd=0, highlightthickness=0).pack(side="left")
        self.port_hint = self.label(self.root, "", color=MUTED, size=9)

        plot_panel = tk.Frame(self.root, bg=PANEL, highlightbackground=GRID, highlightthickness=1)
        plot_panel.pack(fill="both", expand=True, padx=24)
        plot_header = tk.Frame(plot_panel, bg=PANEL)
        plot_header.pack(fill="x", padx=16, pady=10)
        for title, key in (("频率", "hz"), ("点数", "points"), ("最近点", "near")):
            self.label(plot_header, title, color=MUTED, size=9).pack(side="left", padx=(0, 6))
            self.label(plot_header, variable=self.stats[key], bold=True).pack(side="left", padx=(0, 22))
        self.plot_note = self.label(plot_header, "0° 朝上 · 顺时针", color=MUTED, size=9)
        self.plot_note.pack(side="right")
        self.canvas = tk.Canvas(plot_panel, bg=PLOT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.clear_hover)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.label(plot_panel, variable=self.cursor_text, color=MUTED, size=9).pack(pady=8)

        diagnostics = tk.Frame(self.root, bg=BG)
        diagnostics.pack(fill="x", padx=24, pady=(10, 5))
        self.label(diagnostics, variable=self.status, color=ACCENT, size=9).pack(side="left")
        for title, key in (("帧", "frames"), ("CRC/格式", "crc"), ("字节", "bytes"), ("速率", "rate"), ("丢块", "drop")):
            self.label(diagnostics, title, color=MUTED, size=9).pack(side="left", padx=(18, 5))
            self.label(diagnostics, variable=self.stats[key], size=9).pack(side="left")
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=24, pady=(0, 12))
        self.label(footer, variable=self.detail, color=MUTED, size=9,
                   wraplength=1030, justify="left").pack(anchor="w")

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
        except ImportError:
            self.port_hint.config(text="缺少 pyserial；模拟预览仍可使用。")
            return
        self.port_box["values"] = [p.device for p in ports]
        if not self.port.get() and ports:
            self.port.set(ports[0].device)
        self.port_hint.config(text=" / ".join(f"{p.device}: {p.description}" for p in ports)
                              if ports else "未发现串口，可连接设备后刷新或手动输入 COM 号。")

    def reset_session(self):
        self.parser = Parser()
        self.scan.clear()
        self.byte_count = self.rate_bytes = 0
        self.rate = 0
        self.last_dropped = 0
        self.range_changed_at = 0
        self.started = self.rate_time = time.monotonic()
        self.paused = False
        self.frozen = self.visible = ()
        self.pause_button.config(text="暂停画面")

    def toggle_connection(self):
        if self.worker:
            self.worker.stop()
            self.mode = "stopping"
            self.connect_button.config(text="正在断开…", state="disabled")
            return
        if not self.port.get().strip():
            messagebox.showinfo("选择串口", "请连接 PWLINK2 后刷新串口，或手动输入 COM 号。")
            return
        try:
            import serial  # noqa: F401
        except ImportError:
            messagebox.showerror("缺少串口依赖", "请在此文件夹运行：\npython -m pip install -r requirements.txt")
            return
        self.demo_source = None
        self.reset_session()
        self.mode = "connecting"
        self.worker = Receiver(self.port.get().strip())
        self.connect_button.config(text="取消连接")
        self.demo_button.config(text="模拟预览", state="disabled")
        self.port_box.config(state="disabled")
        self.refresh_button.config(state="disabled")
        self.status.set("正在打开串口…")
        self.detail.set("若端口被占用，请先关闭 PowerWriter / SSCOM 的串口连接。")
        self.worker.start()

    def toggle_demo(self):
        if self.worker:
            return
        if self.mode == "demo":
            self.demo_source = None
            self.mode = "idle"
            self.clear()
            self.status.set("模拟已停止")
            self.detail.set("可选择串口连接实物雷达。")
            self.demo_button.config(text="模拟预览")
        else:
            self.reset_session()
            self.demo_source = Demo()
            self.demo_next = time.monotonic()
            self.mode = "demo"
            self.demo_button.config(text="停止模拟")
            self.status.set("模拟预览 · 合成房间与障碍物")
            self.detail.set("当前为模拟数据。接入实物时选择 COM 端口，再点击“连接雷达”。")

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.frozen_at = time.monotonic()
            self.frozen = self.scan.snapshot(self.frozen_at, float(self.retention.get()))
            self.frozen_angle = self.scan.latest_angle
        self.pause_button.config(text="继续显示" if self.paused else "暂停画面")

    def clear(self):
        self.scan.clear()
        self.frozen = self.visible = ()

    def feed(self, data, received_at):
        self.byte_count += len(data)
        for packet in self.parser.feed(data):
            self.scan.add(packet, received_at)

    def _read_worker(self):
        worker = self.worker
        if not worker:
            return
        # A lost raw chunk breaks frame continuity. Drop any partial packet,
        # while keeping cumulative diagnostics, before searching for a header.
        if worker.dropped_chunks != self.last_dropped:
            self.parser.buffer.clear()
            self.last_dropped = worker.dropped_chunks
        deadline = time.monotonic() + 0.012
        while time.monotonic() < deadline:
            try:
                received_at, data = worker.data.get_nowait()
            except queue.Empty:
                break
            self.feed(data, received_at)
        while True:
            try:
                event, value = worker.events.get_nowait()
            except queue.Empty:
                break
            if event == "opened" and self.mode != "stopping":
                self.mode = "serial"
                self.connect_button.config(text="断开连接")
            elif event == "error":
                self.status.set("串口连接失败 / 中断")
                self.detail.set(f"{value}。检查 COM 号、USB 连接，并关闭其他占用此端口的软件。")
            elif event == "closed":
                if self.mode == "stopping":
                    self.status.set("已断开串口")
                    self.detail.set("可重新连接或使用模拟预览。")
                self.mode = "idle"
                self.worker = None
                self.clear()
                self.connect_button.config(text="连接雷达", state="normal")
                self.demo_button.config(state="normal")
                self.port_box.config(state="normal")
                self.refresh_button.config(state="normal")

    def tick(self):
        if self.closed:
            return
        now = time.monotonic()
        self._read_worker()
        if self.mode == "demo":
            count = min(30, max(0, int((now - self.demo_next) * 375) + 1))
            for _ in range(count):
                self.feed(self.demo_source.frame(), now)
            self.demo_next += count / 375
            if now - self.demo_next > 0.2:
                self.demo_next = now
        elapsed = now - self.rate_time
        if elapsed >= 0.5:
            self.rate = (self.byte_count - self.rate_bytes) / elapsed / 1024
            self.rate_bytes, self.rate_time = self.byte_count, now
        live = self.scan.snapshot(now, float(self.retention.get()))
        samples = self.frozen if self.paused else live
        minimum = int(self.confidence.get())
        eligible = tuple(s for s in samples if s.point.confidence >= minimum and s.point.distance_mm > 0)
        if self.radius.get() == "自动":
            if eligible:
                target = fitted_radius(eligible)
                if target > self.display_radius or (target != self.display_radius and now - self.range_changed_at > 1.5):
                    self.display_radius = target
                    self.range_changed_at = now
        else:
            self.display_radius = float(self.radius.get())
        radius = self.display_radius
        self.visible = tuple(s for s in eligible if s.point.distance_mm <= radius * 1000)
        self.view_rotation = float(self.rotation.get())
        fresh = self.scan.last_packet_at is not None and now - self.scan.last_packet_at < 1
        hz = self.scan.speed_dps / 360 if fresh else 0
        self.stats["hz"].set(f"{hz:.1f} Hz" if fresh else "— Hz")
        self.stats["points"].set(str(len(self.visible)))
        nearest = min((s.point.distance_mm for s in self.visible), default=None)
        self.stats["near"].set(distance_text(nearest / 1000) if nearest is not None else "—")
        self.stats["frames"].set(f"{self.parser.frames:,}")
        self.stats["crc"].set(f"{self.parser.crc_errors} / {self.parser.format_errors}")
        received = self.worker.received_bytes if self.worker else self.byte_count
        self.stats["bytes"].set(f"{received:,}")
        self.stats["rate"].set(f"{self.rate:.1f} KB/s")
        self.stats["drop"].set(str(self.worker.dropped_chunks if self.worker else 0))
        if self.mode == "serial":
            if fresh:
                self.status.set(f"正在接收 · {self.worker.port} · 230400 baud")
                self.detail.set("雷达显示同一高度的水平截面；“前方”为画面上方，可用“旋转”对齐实物方向。滚轮可缩放，移到回波上查看距离。")
            elif now - self.started > 2:
                self.status.set("已打开串口 · 等待有效 LD06 数据")
                self.detail.set("已有字节但无有效帧时，检查设备型号与串口链路；没有字节时，检查供电、共地及雷达 TX → 适配器 RX。")
            else:
                self.status.set("串口已打开 · 等待数据…")
        badge, color = {"idle": ("未连接", MUTED), "demo": ("模拟数据", AMBER),
                        "connecting": ("正在连接", AMBER), "stopping": ("正在断开", AMBER),
                        "serial": ("实时接收" if fresh else "等待数据", ACCENT if fresh else AMBER)}[self.mode]
        if self.paused:
            badge += " / 画面暂停"
        self.badge.config(text=f"●  {badge}", fg=color)
        self.plot_note.config(text=f"半径 {distance_text(radius)} · 上方为显示前向")
        self.draw(now, radius)
        self.timer = self.root.after(33, self.tick)

    def geometry(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return w / 2, h / 2, max(1, min(w, h) / 2 - 64)

    def draw(self, now, radius):
        canvas = self.canvas
        cx, cy, outer = self.geometry()
        signature = (canvas.winfo_width(), canvas.winfo_height(), radius)
        if signature != self.grid_signature:
            canvas.delete("grid")
            for i in range(1, 5):
                r = outer * i / 4
                canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=GRID, tags="grid")
                ring_label = f"{radius*i*100/4:g} cm" if radius <= 1 else f"{radius*i/4:g} m"
                canvas.create_text(cx+8, cy-r+11, text=ring_label, anchor="w",
                                   fill=MUTED, font=("Segoe UI", 8), tags="grid")
            for degrees in range(0, 360, 45):
                a = math.radians(degrees)
                sx, sy = math.sin(a), -math.cos(a)
                canvas.create_line(cx, cy, cx+outer*sx, cy+outer*sy,
                                   fill=GRID, dash=(2, 5), tags="grid")
            self.grid_signature = signature
        canvas.delete("live")
        def pixel(sample):
            x, y = xy(sample.point, self.view_rotation)
            return cx + x / radius * outer, cy - y / radius * outer

        if self.show_contours.get():
            groups = contours(self.visible, self.view_rotation)
            # Fill each continuous measured sector separately. Never fill across
            # an angular gap or infer a surface between unrelated returns.
            for group in groups:
                if len(group) >= 3:
                    coordinates = [value for sample in group for value in pixel(sample)]
                    canvas.create_polygon(cx, cy, *coordinates, fill="#eff6ff", outline="", tags="live")
            canvas.tag_raise("grid")
            for group in groups:
                if len(group) >= 2:
                    coordinates = [value for sample in group for value in pixel(sample)]
                    canvas.create_line(*coordinates, fill=ACCENT, width=2.5,
                                       capstyle="round", joinstyle="round", tags="live")
                else:
                    px, py = pixel(group[0])
                    canvas.create_oval(px-2, py-2, px+2, py+2, fill="#9fb9e9", outline="", tags="live")
        else:
            retention = float(self.retention.get())
            sample_time = self.frozen_at if self.paused else now
            for sample in self.visible:
                px, py = pixel(sample)
                age = max(0, sample_time - sample.received_at) / retention
                color = ACCENT if age < 0.2 else "#6090e8" if age < 0.65 else "#a7c1ee"
                canvas.create_oval(px-2, py-2, px+2, py+2, fill=color, outline="", tags="live")

        directions = directional_distances(self.visible, self.view_rotation)
        for title, x, y, anchor in (("前方", cx, cy-outer-18, "s"),
                                     ("后方", cx, cy+outer+18, "n"),
                                     ("左侧", cx-outer-18, cy, "e"),
                                     ("右侧", cx+outer+18, cy, "w")):
            canvas.create_text(x, y, text=f"{title}\n{distance_text(directions[title])}",
                               fill=TEXT, anchor=anchor, justify="center",
                               font=("Microsoft YaHei UI", 10), tags="live")
        canvas.create_oval(cx-9, cy-9, cx+9, cy+9, fill=TEXT, outline=PLOT, width=2, tags="live")
        canvas.create_polygon(cx, cy-16, cx-4, cy-9, cx+4, cy-9, fill=TEXT, tags="live")
        canvas.create_text(cx, cy+22, text="雷达", fill=MUTED, font=("Microsoft YaHei UI", 8), tags="live")
        if self.visible:
            nearest = min(self.visible, key=lambda sample: sample.point.distance_mm)
            px, py = pixel(nearest)
            canvas.create_oval(px-5, py-5, px+5, py+5, fill="#ed8936", outline=PANEL, width=1.5, tags="live")
            sign = 1 if px >= cx else -1
            label_x, label_y = px + sign*28, py - 22
            canvas.create_line(px, py, label_x, label_y+7, fill="#ed8936", tags="live")
            canvas.create_text(label_x, label_y, anchor="w" if sign > 0 else "e",
                               text=f"最近 {distance_text(nearest.point.distance_mm / 1000)}",
                               fill="#b45309", font=("Microsoft YaHei UI", 10, "bold"), tags="live")
        if not self.visible:
            canvas.create_text(cx, cy+36, text="等待扫描点云" if self.mode != "demo" else "正在生成模拟点云",
                               fill=MUTED, font=("Microsoft YaHei UI", 11), tags="live")

    def on_motion(self, event):
        cx, cy, outer = self.geometry()
        dx, dy = event.x-cx, cy-event.y
        distance = math.hypot(dx, dy) / outer * self.display_radius
        angle = math.degrees(math.atan2(dx, dy)) % 360
        sensor_angle = (angle - float(self.rotation.get())) % 360
        nearest = min(self.visible, key=lambda s: math.hypot(
            xy(s.point, self.view_rotation)[0] / self.display_radius * outer - dx,
            xy(s.point, self.view_rotation)[1] / self.display_radius * outer - dy), default=None)
        self.canvas.delete("hover")
        if nearest is not None:
            x, y = xy(nearest.point, self.view_rotation)
            px, py = cx + x / self.display_radius * outer, cy - y / self.display_radius * outer
            if math.hypot(px-event.x, py-event.y) <= 14:
                self.canvas.create_oval(px-7, py-7, px+7, py+7, outline=AMBER, width=2, tags="hover")
                self.cursor_text.set(f"回波距离 {distance_text(nearest.point.distance_mm / 1000)}　角度 {nearest.point.angle_deg:.1f}°　强度 {nearest.point.confidence}")
                return
        self.cursor_text.set(f"光标位置 {distance_text(distance)}　显示方位 {angle:.1f}°　雷达角度 {sensor_angle:.1f}°")

    def clear_hover(self, _event=None):
        self.canvas.delete("hover")
        self.cursor_text.set("蓝线：连续回波轮廓　浅蓝：测距扇区　橙点：最近回波")

    def zoom(self, event):
        if not event.delta:
            return
        index = min(range(len(RADII)), key=lambda i: abs(RADII[i] - self.display_radius))
        index = max(0, min(len(RADII)-1, index + (-1 if event.delta > 0 else 1)))
        self.radius.set(f"{RADII[index]:g}")
        self.clear_hover()

    def export(self):
        if not self.visible:
            messagebox.showinfo("没有点云", "当前画面没有可导出的点，请先连接雷达或启动模拟预览。")
            return
        path = filedialog.asksaveasfilename(
            title="导出当前显示点云", defaultextension=".csv",
            initialfile=f"ld06_{'demo' if self.mode == 'demo' else 'serial'}_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV 点云", "*.csv")])
        if not path:
            return
        try:
            self.save_csv(path)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        self.detail.set(f"已导出 {len(self.visible)} 个显示点至 {path}")

    def save_csv(self, path):
        with Path(path).open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.writer(output)
            writer.writerow(("source", "sensor_angle_deg", "distance_mm", "confidence",
                             "display_rotation_deg", "x_m", "y_m"))
            for sample in sorted(self.visible, key=lambda s: s.point.angle_deg):
                x, y = xy(sample.point, self.view_rotation)
                writer.writerow(("demo" if self.mode == "demo" else "serial",
                                 f"{sample.point.angle_deg:.3f}", sample.point.distance_mm,
                                 sample.point.confidence, self.view_rotation, f"{x:.4f}", f"{y:.4f}"))

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=0.5)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="LD06 串口雷达点云 GUI")
    parser.add_argument("--demo", action="store_true", help="启动模拟预览")
    parser.add_argument("--port", help="打开指定串口，例如 COM7")
    args = parser.parse_args()
    if args.demo and args.port:
        parser.error("--demo 与 --port 请选择一种")
    root = tk.Tk()
    app = RadarApp(root)
    if args.demo:
        app.toggle_demo()
    elif args.port:
        app.port.set(args.port)
        app.toggle_connection()
    root.mainloop()


if __name__ == "__main__":
    main()
