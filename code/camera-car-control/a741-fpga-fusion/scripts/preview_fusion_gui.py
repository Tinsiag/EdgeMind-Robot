"""Render the disconnected GUI with a labelled synthetic map for visual QA."""
from pathlib import Path
import sys
import tkinter as tk
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"host"))
from app import App
from fusion import NavigationStatus


def main():
    root=tk.Tk();app=App(root,sensors_only=True)
    try:
        root.title("A741 FPGA Fusion - OFFLINE synthetic preview")
        raw=bytearray(4096)
        for y in range(12,116):
            for x in range(12,116):
                value=2 if x in (12,115) or y in (12,115) else 1
                i=y*128+x;raw[i//4]|=value<<((i%4)*2)
        app.sensor_tabs.select(app.fusion_view.frame)
        app.fusion_view.update({"raw":bytes(raw),"initial":(0,0,0),"target":(1000,800,90),
            "status":NavigationStatus(0,0,0x16,0,0,0,1000,1,0,0,0,0)})
        output=ROOT/".local/gui-preview";output.mkdir(parents=True,exist_ok=True)
        for size in ("1280x850","1000x720"):
            root.geometry(size+"+20+20");root.update();root.after(100);root.update()
            bounds=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())
            ImageGrab.grab(bbox=bounds).save(output/(size+".png"))
            print(output/(size+".png"))
    finally:
        app.shutdown.set();app.cancel.set();app.thread.join(timeout=2);app.mapper.close();app.logfile.close();root.destroy()


if __name__=="__main__":main()
