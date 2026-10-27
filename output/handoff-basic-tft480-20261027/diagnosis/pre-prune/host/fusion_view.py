"""Tk views for the map and navigation executed by FPGA RTL."""
import json
from dataclasses import replace
import math
from pathlib import Path
import time
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk
from fusion import load_map, map_record, NavigationStatus


class FusionView:
    def __init__(self, app, notebook):
        self.app=app;self.raw=None;self.status=None;self.initial=None;self.target=None;self.photo=None;self.waypoints=[]
        self.updated=0;self.last_live_sequence=None
        self.geometry=json.loads((Path(__file__).resolve().parents[1]/"config/geometry.json").read_text(encoding="utf-8"))
        self.frame=ttk.Frame(notebook);notebook.add(self.frame,text="FPGA地图 / 导航")
        self.frame.columnconfigure(0,weight=1);self.frame.rowconfigure(2,weight=1)
        toolbar=ttk.Frame(self.frame);toolbar.grid(row=0,column=0,sticky="ew")
        for i,(text,kind) in enumerate((("新建地图","build"),("结束建图","freeze"),("下载","download"),("上传","upload"),("保存","save"),("清空","clear"))):
            ttk.Button(toolbar,text=text,command=lambda k=kind:self.action(k),width=7).grid(row=0,column=i,sticky="ew",padx=1,pady=3)
        for i in range(6):toolbar.columnconfigure(i,weight=1)
        position=ttk.Frame(self.frame);position.grid(row=1,column=0,sticky="ew")
        self.mode=tk.StringVar(value="goal")
        for i,(text,value) in enumerate((("初始位姿","pose"),("目标点","goal"))):
            ttk.Radiobutton(position,text=text,variable=self.mode,value=value).grid(row=0,column=i,padx=4)
        ttk.Label(position,text="朝向(°)").grid(row=0,column=2);self.degrees=tk.DoubleVar(value=0)
        ttk.Spinbox(position,from_=-180,to=180,increment=15,textvariable=self.degrees,width=6).grid(row=0,column=3)
        ttk.Button(position,text="开始导航",command=lambda:self.action("navigate")).grid(row=1,column=0,sticky="ew",padx=2,pady=3)
        ttk.Button(position,text="返回起点",command=lambda:self.action("return")).grid(row=1,column=1,sticky="ew",padx=2,pady=3)
        ttk.Button(position,text="取消 / 停止",command=app.stop).grid(row=1,column=2,columnspan=2,sticky="ew",padx=2,pady=3)
        ttk.Radiobutton(position,text="添加路径点",variable=self.mode,value="waypoint").grid(row=2,column=0,sticky="w")
        ttk.Button(position,text="执行路径点",command=lambda:self.action("mission")).grid(row=2,column=1,sticky="ew")
        ttk.Button(position,text="清空路径点",command=lambda:self.action("clear_waypoints")).grid(row=2,column=2,sticky="ew")
        self.mission_text=tk.StringVar(value="路径点 0/16")
        ttk.Label(position,textvariable=self.mission_text).grid(row=3,column=0,columnspan=4,sticky="w")
        for i in range(4):position.columnconfigure(i,weight=1)
        self.canvas=tk.Canvas(self.frame,width=320,height=260,background="#edf0f2",highlightthickness=0)
        self.canvas.grid(row=2,column=0,sticky="nsew");self.canvas.bind("<Button-1>",self.select);self.canvas.bind("<Configure>",lambda _:self.draw())
        self.summary=tk.StringVar(value="未加载FPGA地图；几何基准待核实")
        ttk.Label(self.frame,textvariable=self.summary,wraplength=320).grid(row=3,column=0,sticky="ew")

    def action(self, kind):
        if kind=="clear_waypoints":
            if getattr(self.app,"busy",False):return
            self.waypoints.clear();self.mission_text.set("路径点 0/16");self.draw();return
        if kind=="mission":
            if not self.waypoints:
                messagebox.showerror("路径点","请先在地图上添加路径点");return
            self.app.submit("fusion","mission",tuple(self.waypoints));return
        if kind=="save":
            if self.raw is None:
                messagebox.showerror("地图","请先下载FPGA地图");return
            path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("FPGA地图","*.json")])
            if not path:return
            record=map_record(self.raw,self.app.calibration,self.geometry,self.status)
            Path(path).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
            image=self.map_image();image.transpose(Image.Transpose.TRANSVERSE).save(Path(path).with_suffix(".png"))
            image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(Path(path).with_suffix(".pgm"))
            Path(path).with_suffix(".yaml").write_text("image: "+Path(path).with_suffix(".pgm").name+"\nresolution: 0.05\norigin: [-3.2, -3.2, 0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n",encoding="utf-8")
            self.app.log("message",{"fpga_map_saved":path,"crc32":record["crc32"]});return
        if kind=="upload":
            path=filedialog.askopenfilename(filetypes=[("FPGA地图","*.json")])
            if path:
                try:raw=load_map(path)
                except Exception as exc:messagebox.showerror("地图",str(exc));return
                self.app.submit("fusion",kind,raw)
            return
        if kind=="return":
            if self.initial is None:
                messagebox.showerror("导航","本会话没有确认的起始位姿");return
            self.app.submit("fusion",kind,*self.initial);return
        self.app.submit("fusion",kind)

    def select(self,event):
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height());size=min(width,height)
        ox=(width-size)/2;oy=(height-size)/2
        x=3200-(event.y-oy)*6400/size;y=3200-(event.x-ox)*6400/size
        if not (-3200<=x<3200 and -3200<=y<3200):return
        try:
            angle=float(self.degrees.get())
            if not math.isfinite(angle):raise ValueError()
        except Exception:messagebox.showerror("朝向","请输入有效角度");return
        if self.mode.get()=="waypoint":
            if getattr(self.app,"busy",False):return
            if len(self.waypoints)>=16:
                messagebox.showerror("路径点","最多16个路径点");return
            if not (-3100<=x<=3100 and -3100<=y<=3100):return
            self.waypoints.append((x,y,angle));self.mission_text.set(f"路径点 {len(self.waypoints)}/16");self.draw();return
        self.app.submit("fusion",self.mode.get(),x,y,angle)

    def update(self,value):
        if "mission" in value:
            m=value["mission"]
            self.mission_text.set(f"路径点 {min(m.index+int(m.active),m.count)}/{m.count}  {'运行' if m.active else '停止'}  原因 {m.error}")
        if "raw" in value:self.raw=value["raw"]
        if "status" in value:self.status=value["status"];self.updated=time.monotonic()
        if "initial" in value:self.initial=value["initial"]
        if "target" in value:self.target=value["target"]
        if self.status:
            s=self.status
            self.summary.set(f"FPGA 位姿 {s.x_mm}/{s.y_mm} mm  {s.yaw_raw*360/65536:.1f}°  匹配 {s.quality}%  状态 {s.state}  原因 {s.fault}  地图 v{s.map_revision}  几何 {'已核实' if s.geometry_verified else '锁定'}")
        else:self.summary.set("位姿无效 / 过期；已下载地图保留")
        self.draw()

    def update_live(self, value):
        if time.monotonic()-value["host_monotonic"]>.15 or value["seq"]==self.last_live_sequence:
            return
        self.last_live_sequence=value["seq"]
        previous=self.status or NavigationStatus(0,0,0,0,0,0,65535,0,0,0,0,0)
        status=replace(previous,state=value["state"],fault=value["fault"],x_mm=value["x_mm"],y_mm=value["y_mm"],
            yaw_raw=value["yaw_raw"],front_mm=value["front_mm"],map_revision=value["map_revision"],quality=value["quality"],
            flags=(previous.flags&0x7f)|(0x80 if value["geometry_verified"] else 0))
        self.update({"status":status})

    def expire(self):
        if self.status and time.monotonic()-self.updated>.75:
            self.update({"status":None})

    def map_image(self):
        levels=(127,255,0,80)
        pixels=bytes(levels[(self.raw[i//4]>>((i%4)*2))&3] for i in range(16384))
        return Image.frombytes("L",(128,128),pixels)

    def draw(self):
        self.canvas.delete("all");width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height());size=max(1,min(width,height));ox=(width-size)/2;oy=(height-size)/2
        if self.raw:
            image=self.map_image().transpose(Image.Transpose.TRANSVERSE).resize((size,size),Image.Resampling.NEAREST)
            self.photo=ImageTk.PhotoImage(image);self.canvas.create_image(ox,oy,image=self.photo,anchor="nw")
        for item,color in ((self.initial,"#218748"),(self.target,"#d14e23")):
            if item:
                x,y,_=item;sx=ox+(3200-y)*size/6400;sy=oy+(3200-x)*size/6400
                self.canvas.create_oval(sx-4,sy-4,sx+4,sy+4,fill=color,outline=color)
        for number,(x,y,_) in enumerate(self.waypoints,1):
            sx=ox+(3200-y)*size/6400;sy=oy+(3200-x)*size/6400
            self.canvas.create_oval(sx-6,sy-6,sx+6,sy+6,fill="#6846ad",outline="white")
            self.canvas.create_text(sx,sy,text=str(number),fill="white",font=("TkDefaultFont",8))
        if self.status:
            s=self.status;sx=ox+(3200-s.y_mm)*size/6400;sy=oy+(3200-s.x_mm)*size/6400;a=s.yaw_raw*2*math.pi/65536
            self.canvas.create_line(sx,sy,sx-math.sin(a)*18,sy-math.cos(a)*18,fill="#1b68ae",width=3,arrow="last")
        scale=size/6.4;self.canvas.create_line(ox+12,oy+size-15,ox+12+scale,oy+size-15,fill="#555",width=2)
        self.canvas.create_text(ox+12+scale/2,oy+size-25,text="1 m",fill="#555")


def execute_fusion(app, action, args):
    client=app.client
    if action=="build":
        client.map_begin(build=True);client.prepare_lidar(app.calibration,app.cancel);app.lidar_requested=True
        app.events.put(("message","FPGA建图已开始；人工驾驶探索"))
    elif action=="freeze":
        crc=client.map_commit();app.events.put(("message",{"fpga_map_crc32":crc}))
    elif action=="clear":client.map_begin()
    elif action=="download":app.events.put(("fusion",{"raw":client.download_map(app.cancel)}))
    elif action=="upload":client.upload_map(args[0],app.cancel);app.events.put(("fusion",{"raw":args[0]}))
    elif action=="pose":
        client.set_initial_pose(*args);app.events.put(("fusion",{"initial":args}));client.prepare_lidar(app.calibration,app.cancel);app.lidar_requested=True
    elif action=="goal":client.goal(*args);app.events.put(("fusion",{"target":args}))
    elif action=="mission":
        result=client.run_waypoints(app.calibration,args[0],app.cancel,lambda value:app.events.put(("fusion",{"mission":value})))
        app.events.put(("message",{"waypoint_mission_finished":vars(result)}));app.lidar_requested=False
    elif action in ("navigate","return"):
        target=tuple(args) if action=="return" else app.fusion_view.target
        if target is None:raise ValueError("请先在地图中选择目标点")
        if action=="return":app.events.put(("fusion",{"target":target}))
        result=client.run_waypoints(app.calibration,[target],app.cancel,
            lambda value:app.events.put(("fusion",{"mission":value})))
        app.events.put(("message",{"navigation_finished":vars(result)}));app.lidar_requested=False
    app.events.put(("fusion",{"status":client.navigation_status()}))
