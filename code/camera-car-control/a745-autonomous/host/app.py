"""Passive telemetry viewer. Motion is operated only on the FPGA buttons."""
import tkinter as tk
from tkinter import ttk
from receiver import Receiver

class App:
    def __init__(self,root):
        self.root=root;self.receiver=None;root.title('EdgeMind A745 · 自主避障遥测');root.geometry('720x500')
        frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='S1 启动 / 停止自主避障；S0 硬件复位急停。\n本窗口只接收数据，不能启动或停止电机。',wraplength=660).pack(anchor='w')
        self.message=tk.StringVar(value='未接收');self.status=tk.StringVar(value='等待 FPGA UDP 6103 遥测')
        ttk.Button(frame,text='接收遥测',command=self.receive).pack(anchor='w',pady=12)
        ttk.Label(frame,textvariable=self.status,font=('Consolas',12),justify='left').pack(anchor='w')
        ttk.Label(frame,textvariable=self.message,wraplength=660).pack(anchor='w',pady=12)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)
    def receive(self):
        if self.receiver:return
        try:self.receiver=Receiver();self.message.set('正在被动监听；没有向 FPGA 发送命令')
        except OSError as exc:self.message.set(str(exc))
    def poll(self):
        if self.receiver:
            s,a=self.receiver.read()
            if not s:self.status.set('遥测未收到或已过期；硬件当前状态未知')
            else:
                text=f"ARM {'ON' if s['armed'] else 'OFF'}   状态 {s['state']}   故障 0x{s['faults']:04X}\n"
                text+=f"目标 {s['targets']} mm/s\n轮速 {s['speeds']} mm/s   编码器 {s['counts']}\n"
                if s['revision']>=74507:
                    text+=f"无脉冲提示 左 {'有' if s['encoder_no_pulse_left'] else '无'} / 右 {'有' if s['encoder_no_pulse_right'] else '无'}\n"
                text+=f"前 / 左 / 右 {s['ranges']} mm\nDDR {'OK' if s['ddr_ready'] else 'WAIT'}   完整视频帧 {s['video_frames']}\n"
                if s['revision']>=74504:
                    text+=f"转弯空间 左 {'通' if s['left_clear'] else '阻'} / 右 {'通' if s['right_clear'] else '阻'}  后方 {s['rear']} mm\n"
                text+=f"CAM {'READY' if s['camera_ready'] else 'WAIT/FAIL'}  阶段 {s['camera_phase']}  尝试 {s['camera_attempt']}\n"
                text+=f"CAM 错误 {s['camera_error']:02X}   寄存器 {s['camera_register']:04X}\n期望 {s['camera_expected']:02X} / 读回 {s['camera_value']:02X}"
                if a:
                    text+=f"\nROLL {a['roll']:.1f}°  PITCH {a['pitch']:.1f}°  YAW {s['yaw']:.1f}°"
                    text+=f"\nFW {s['revision']}   CPU {'OK' if a['cpu_alive'] else 'WAIT/FAULT'}   进度 {a['cpu_progress']}"
                self.status.set(text)
        self.root.after(100,self.poll)
    def close(self):
        if self.receiver:self.receiver.close()
        self.root.destroy()
if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
