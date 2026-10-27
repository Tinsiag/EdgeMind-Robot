"""Debug data and explicit basic-avoidance controls. Video is on the TFT only."""
import argparse
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from avoidance import AvoidanceClient
from calibration import Calibration
from telemetry import TelemetryReceiver


def service_action(client, calibration, action, cancel, sensors_only=False):
    """Called by the sole socket owner; connection never starts motion."""
    if action=="connect":
        return client.connect(calibration)
    if action=="stop":
        try:
            return client.stop()
        finally:
            client.disarm()
    if cancel.is_set():
        raise RuntimeError("操作已取消")
    if action=="calibrate":
        client.disarm()
        return client.calibrate(cancel)
    if action in ("arm","start") and sensors_only:
        raise RuntimeError("只读调试模式禁止 ARM 和运动")
    if action=="arm":
        return client.arm(calibration)
    if action=="start":
        return client.start_avoidance()
    if action=="lidar":
        return client.lidar(calibration.data.get("lidar_duty_permille",400))
    if action=="clear":
        client.stop();client.disarm()
        result=client.command(0x21)
        if client.status().faults:
            raise RuntimeError("故障仍存在；检查传感器、编码器和停止条件")
        return result
    raise ValueError("未知调试操作")


def status_text(basic, snap, rtt):
    tilt=(f"ROLL {basic.roll_raw*180/32768:7.2f}°  PITCH {basic.pitch_raw*180/32768:7.2f}°"
          if basic.tilt_valid else "ROLL / PITCH 无效")
    yaw=f"YAW  {basic.yaw_raw*180/32768:7.2f}°" if basic.yaw_valid else "YAW 无效"
    state={0:"待机",1:"巡航",2:"左转",3:"右转",4:"受阻",5:"雷达无效"}.get(basic.state,"未知")
    ranges=(f"{basic.front_mm} / {basic.left_mm} / {basic.right_mm} mm"
            if basic.flags&2 else "雷达数据无效")
    cpu="故障" if basic.cpu_flags&2 else "运行" if basic.cpu_flags&1 else "失效"
    text=f"{tilt}\n{yaw}\n\n前/左/右: {ranges}\n避障: {state}  原因: {basic.fault}  CPU: {cpu}\nRTT: {rtt:.1f} ms"
    if snap:
        text+=f"\nARM: {'已解锁' if snap.flags&32 else '未解锁'}  轮速: {snap.left_speed}/{snap.right_speed} mm/s  故障: 0x{snap.faults:04X}"
    else:
        text+="\n轮速 / ARM / 电机故障遥测已过期，状态未知"
    return text


class App:
    def __init__(self, root, sensors_only=False):
        self.root=root;self.sensors_only=sensors_only
        self.calibration=Calibration.load()
        self.jobs=queue.Queue(maxsize=1);self.events=queue.Queue()
        self.closed=threading.Event();self.cancel=threading.Event()
        self.action_lock=threading.Lock();self.stop_epoch=0;self.stop_pending=False;self.busy=False
        self.ui_seen=time.monotonic();self.last_status=None
        self.root.title("EdgeMind · TFT 视频 / 姿态 / 雷达避障调试")
        self.root.geometry("720x540")
        page=ttk.Frame(root,padding=16);page.pack(fill="both",expand=True)
        self.peer=tk.StringVar(value="192.168.0.2")
        row=ttk.Frame(page);row.pack(fill="x")
        ttk.Label(row,text="FPGA IP").pack(side="left")
        ttk.Entry(row,textvariable=self.peer,width=20).pack(side="left",padx=8)
        ttk.Button(row,text="连接",command=lambda:self.submit("connect")).pack(side="left")
        ttk.Label(page,text="网口仅传调试数据；摄像头视频与姿态文字显示在 480×272 TFT。",wraplength=660).pack(anchor="w",pady=14)
        buttons=ttk.Frame(page);buttons.pack(fill="x")
        for label,action in [("启动雷达","lidar"),("静止校准","calibrate"),("ARM（不移动）","arm"),("启动避障","start"),("清除故障","clear")]:
            ttk.Button(buttons,text=label,command=lambda a=action:self.submit(a)).pack(side="left",padx=2)
        ttk.Button(page,text="停止并解除 ARM",command=self.stop).pack(fill="x",pady=10)
        self.status=tk.StringVar(value="未连接；默认未 ARM")
        ttk.Label(page,textvariable=self.status,justify="left",font=("Consolas",13)).pack(anchor="nw",pady=10)
        self.message=tk.StringVar(value="连接后按需启动雷达、静止校准、ARM，再手动启动避障。")
        ttk.Label(page,textvariable=self.message,wraplength=660).pack(anchor="w",pady=10)
        self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start()
        root.protocol("WM_DELETE_WINDOW",self.close);root.after(100,self.poll)

    def submit(self, action):
        if self.sensors_only and action in ("arm","start"):
            self.message.set("只读调试模式禁止 ARM 和运动");return
        with self.action_lock:
            if self.stop_pending or self.busy:
                self.message.set("上一操作未完成，请等待；停止按钮始终可用");return
            self.jobs.put_nowait((action,self.peer.get(),self.stop_epoch));self.busy=True

    def stop(self):
        with self.action_lock:
            self.cancel.set();self.stop_epoch+=1;self.stop_pending=True;self.busy=True
            while True:
                try:self.jobs.get_nowait()
                except queue.Empty:break
            self.jobs.put_nowait(("stop",self.peer.get(),self.stop_epoch))

    def worker(self):
        client=telemetry=None;last_poll=0
        def disconnect():
            nonlocal client,telemetry
            if client:
                try:service_action(client,self.calibration,"stop",self.cancel)
                except Exception:pass
                client.close();client=None
            if telemetry:telemetry.close();telemetry=None
            self.events.put(("disconnected",None))
            with self.action_lock:
                self.cancel.set();self.stop_pending=False;self.busy=False
                while True:
                    try:self.jobs.get_nowait()
                    except queue.Empty:break
        try:
            while not self.closed.wait(.04):
                action=None;epoch=None
                with self.action_lock:
                    if self.closed.is_set():return
                    try:
                        action,peer,epoch=self.jobs.get_nowait()
                        # STOP and dequeue share this lock: a later submit cannot
                        # clear cancellation of an operation already in flight.
                        if action!="stop":self.cancel.clear()
                    except queue.Empty:pass
                try:
                    if client and time.monotonic()-self.ui_seen>.5:
                        raise TimeoutError("界面响应超时，控制会话已关闭；须重新连接")
                    if action=="connect":
                        disconnect()
                        if self.closed.is_set():continue
                        with self.action_lock:
                            if epoch!=self.stop_epoch:continue
                            self.cancel.clear();self.busy=True
                        client=AvoidanceClient(peer);client.sensors_only=self.sensors_only
                        service_action(client,self.calibration,action,self.cancel,self.sensors_only)
                        telemetry=TelemetryReceiver(peer)
                        self.events.put(("message","已连接并停止；未 ARM"))
                    elif action:
                        if not client:raise RuntimeError("请先连接 FPGA")
                        service_action(client,self.calibration,action,self.cancel,self.sensors_only)
                        self.events.put(("message",f"{action} 操作完成"))
                    if client and not self.cancel.is_set():
                        client.heartbeat()
                        if time.monotonic()-last_poll>=.2:
                            basic=client.avoidance_status();snap,_=telemetry.read()
                            last_poll=time.monotonic()
                            self.events.put(("status",(basic,snap,client.diag.rtt_ms,last_poll)))
                except Exception as exc:
                    self.events.put(("message",str(exc)))
                    if action=="connect" or isinstance(exc,(OSError,TimeoutError)):
                        disconnect()
                finally:
                    if action:
                        with self.action_lock:
                            if epoch==self.stop_epoch:
                                self.busy=False
                                if action=="stop":self.stop_pending=False;self.cancel.clear()
        finally:
            disconnect()

    def poll(self):
        self.ui_seen=time.monotonic()
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=="message":self.message.set(value)
            elif kind=="disconnected":
                self.last_status=None;self.status.set("未连接；硬件状态未知")
            else:
                basic,snap,rtt,stamp=value;self.last_status=stamp
                self.status.set(status_text(basic,snap,rtt))
        if self.last_status is not None and self.ui_seen-self.last_status>.6:
            self.status.set("状态已过期；姿态、避障和电机状态未知")
        if not self.closed.is_set():self.root.after(100,self.poll)

    def close(self):
        with self.action_lock:
            self.cancel.set();self.closed.set()
        self.thread.join(timeout=1)
        self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensors-only",action="store_true")
    args=parser.parse_args();root=tk.Tk();App(root,args.sensors_only);root.mainloop()


if __name__=="__main__":main()
