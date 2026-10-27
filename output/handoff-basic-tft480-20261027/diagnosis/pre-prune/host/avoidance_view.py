import time
import tkinter as tk
from tkinter import ttk


class AvoidanceView:
    def __init__(self, app, notebook):
        self.app=app;self.last_update=0;self.status=None
        page=ttk.Frame(notebook,padding=8);self.frame=page;notebook.add(page,text="自主避障")
        self.text=tk.StringVar(value="未连接；等待基础状态")
        ttk.Label(page,textvariable=self.text,wraplength=330,justify="left").pack(anchor="nw")
        ttk.Button(page,text="准备 / ARM（不移动）",command=lambda:app.submit("arm")).pack(fill="x",pady=5)
        ttk.Button(page,text="启动自主避障",command=lambda:app.submit("avoidance","start")).pack(fill="x")
        ttk.Button(page,text="停止 / 解除ARM",command=app.stop).pack(fill="x",pady=5)
        ttk.Label(page,text="先完成静止校准、雷达检查与ARM。距离为雷达扇区值，速度为目标值；失联停车。",wraplength=330).pack(anchor="nw")

    def update(self, value):
        status=value.get("status")
        if status is None:return
        self.last_update=time.monotonic();self.status=status;self.app.avoidance_active=status.active
        states={0:"待机",1:"巡航",2:"左转",3:"右转",4:"通道受阻",5:"雷达无效"}
        distance=lambda n:"无效" if n==65535 else f"{n} mm"
        self.text.set(f"{states.get(status.state,'未知')}  原因 {status.fault}\n"
            f"前 {distance(status.front_mm)}\n左 {distance(status.left_mm)} / 右 {distance(status.right_mm)}\n"
            f"CPU {'正常' if status.cpu_flags&1 else '未就绪'}；运行 {status.uptime_ms/1000:.1f} s\n"
            f"手动扫描 {'就绪' if status.flags&4 else '未就绪'}")

    def expire(self):
        if self.last_update and time.monotonic()-self.last_update>1:
            self.text.set("状态过期；检查连接")


def execute_avoidance(app, action):
    if action=="start":
        app.client.start_avoidance();app.avoidance_active=True;app.lidar_requested=True
        app.events.put(("message","自主避障已请求启动；FPGA执行决策"))
    else:
        app.client.stop_avoidance();app.avoidance_active=False
