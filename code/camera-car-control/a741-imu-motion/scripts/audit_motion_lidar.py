"""Audit the compiled motion+LD06 pin map and dynamic motor/PWM paths."""
import json
import re
from pathlib import Path
from audit_imu import PinRows,sha
from check import ROOT


def main():
    build=ROOT / ".local/gowin-motion-lidar"
    result=json.loads((build / "result.json").read_text(encoding="utf-8"))
    if not result["compile_passed"] or result["sources_changed"] or result["motor_locked"] or not result["motion_lidar"]:
        raise RuntimeError("No valid motion+LD06 build")
    for path,digest in result["source_sha256"].items():
        if sha(Path(path))!=digest:raise RuntimeError("Compiler input changed: "+path)
    if sha(Path(result["artifact"]))!=result["artifact_sha256"]:raise RuntimeError("Bitstream changed")
    netlist=build / "impl/gwsynthesis/a741.vg"
    if sha(netlist)!=result["synthesis_netlist_sha256"]:raise RuntimeError("Netlist changed")
    text=netlist.read_text(encoding="utf-8")
    patterns={}
    for name in ("left_in1","left_in2","right_in1","right_in2","lidar_control"):
        start=text.index("OBUF "+name+"_obuf")
        end=text.index(");",start)
        block=text[start:end]
        if ".I(GND)" in block or ".I(VCC)" in block:raise RuntimeError("Dynamic output tied to constant: "+name)
        patterns[name]=block.strip()
    table=PinRows();pin_file=build / "impl/pnr/a741.pin.html"
    table.feed(pin_file.read_text(encoding="utf-8"))
    expected={"lidar_control":("H20/5","out"),"lidar_rx":("H14/4","in"),
              "imu_scl":("L18/5","io"),"imu_sda":("M20/5","io")}
    assigned={}
    for name,(ball,direction) in expected.items():
        rows=[row for row in table.rows if len(row)>17 and row[0]==name]
        if len(rows)!=1 or rows[0][2]!=ball or rows[0][4]!=direction or rows[0][7]!="LVCMOS33":
            raise RuntimeError("Pin/direction mismatch: "+name)
        assigned[name]={"ball_bank":ball,"direction":direction,"io_standard":rows[0][7]}
    if any(row and row[0] in ("tof_sda","tof_scl","tof_xshut") for row in table.rows):
        raise RuntimeError("Absent ToF unexpectedly has physical ports")
    record={"bitstream_sha256":result["artifact_sha256"],"netlist_sha256":sha(netlist),
            "pin_report_sha256":sha(pin_file),"dynamic_outputs":patterns,"assignments":assigned,
            "tof_physical_ports":False,"hardware_tested":False,"timing_signed_off":False}
    (ROOT / "verification/motion-lidar-output-audit.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print("PASS motion/LD06 dynamic output paths, H20/H14 directions, IMU mapping and no ToF pins")


if __name__=="__main__":main()
