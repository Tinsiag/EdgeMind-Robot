"""Isolated HDMI clock diagnostic. Does not access hardware or edit main sources."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FUSION = REPO / "code/camera-car-control/a741-fpga-fusion"
PLATFORM = FUSION / ".local/platform-tft480"
GOWIN = Path("C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe")

top = """`timescale 1ns/1ps
module clock_audit(input wire clk,stop_n,
 output wire tmds_clk_p,tmds_clk_n,
 output wire [2:0] tmds_data_p,tmds_data_n);
 wire serial_clk,pixel_clk,locked;
 A741_Video_PLL video_pll(.clkin(clk),.clkout0(),.clkout1(serial_clk),
  .lock(locked),.mdclk(clk),.reset(!stop_n));
 CLKDIV pixel_divider(.HCLKIN(serial_clk),.RESETN(locked),
  .CLKOUT(pixel_clk),.CALIB(1'b1));
 defparam pixel_divider.DIV_MODE="5";
 a741_hdmi hdmi(.pixel_clk(pixel_clk),.serial_clk(serial_clk),
  .rst_n(stop_n && locked),.rgb(16'hf800),.de(1'b1),.hsync(1'b0),.vsync(1'b0),
  .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
  .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
endmodule
"""
BASELINE = HERE / "baseline-inputs"
inputs = [BASELINE / name for name in ("gowin_pll.v", "gowin_pll_mod.v", "dvi_encoder.v",
                                     "a741_hdmi.v", "reset_sync.v", "pll_init.v")]
cst = "\n".join(line for line in (BASELINE / "clock_audit.cst").read_text().splitlines()
                if re.match(r'IO_(?:LOC|PORT) "(?:clk"|stop_n"|tmds_)', line)) + "\n"
base_sdc = """create_clock -name sys_clk -period 20 [get_ports {clk}]
set_false_path -from [get_ports {stop_n}]
set_false_path -to [get_pins {*reset*/pipe*/CLEAR}]
report_timing -setup -max_paths 50
report_timing -hold -max_paths 50
report_timing -recovery -max_paths 50
report_timing -removal -max_paths 50
"""
generated = """create_generated_clock -name video165m -source [get_ports {clk}] -multiply_by 33 -divide_by 10 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}]
create_generated_clock -name pixel33m -source [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}] -master_clock video165m -divide_by 5 [get_pins {pixel_divider/CLKOUT}]
"""
for mode in (sys.argv[1:] or ["explicit-generated", "auto-derived"]):
    out = HERE / mode
    out.mkdir(parents=True, exist_ok=True)
    listing = []
    for source in inputs:
        target = out / source.name
        shutil.copy2(source, target)
        if mode in ("pixel-domain-reset", "pixel-domain-reset-hold", "pixel-reset-min-delay") and source.name == "a741_hdmi.v":
            target.write_text(target.read_text().replace(
                "reset_sync serial_reset(.clk(serial_clk)",
                "reset_sync serial_reset(.clk(pixel_clk)"))
        if mode == "pixel-falling-reset" and source.name == "a741_hdmi.v":
            target.write_text(target.read_text().replace("wire pixel_n,serial_n;", "wire pixel_n;reg serial_n;").replace(
                "reset_sync serial_reset(.clk(serial_clk),.async_n(rst_n),.rst_n(serial_n));",
                "always @(negedge pixel_clk or negedge rst_n)\n        if(!rst_n) serial_n<=0;else serial_n<=pixel_n;"))
        if mode == "pll-div2-reset" and source.name == "gowin_pll_mod.v":
            target.write_text(target.read_text().replace("ODIV0_SEL = 16", "ODIV0_SEL = 10").replace(
                "ODIV0_FRAC_SEL = 4", "ODIV0_FRAC_SEL = 0"))
        if mode == "pll-div2-reset" and source.name == "a741_hdmi.v":
            target.write_text(target.read_text().replace("pixel_clk,serial_clk,rst_n", "pixel_clk,serial_clk,reset_clk,rst_n").replace(
                "reset_sync serial_reset(.clk(serial_clk)", "reset_sync serial_reset(.clk(reset_clk)"))
        if mode in ("pll-pixel-activehigh-reset", "pll-pixel-activehigh-route1") and source.name == "gowin_pll_mod.v":
            target.write_text(target.read_text().replace("ODIV0_SEL = 16", "ODIV0_SEL = 25").replace(
                "ODIV0_FRAC_SEL = 4", "ODIV0_FRAC_SEL = 0"))
        if mode in ("pll-pixel-activehigh-reset", "pll-pixel-activehigh-route1") and source.name == "a741_hdmi.v":
            target.write_text(target.read_text().replace("pixel_clk,serial_clk,rst_n", "pixel_clk,serial_clk,reset_clk,rst_n").replace(
                "wire pixel_n,serial_n;", "wire pixel_n; (* ASYNC_REG=\"TRUE\" *) reg [2:0] serial_reset_pipe;").replace(
                "reset_sync serial_reset(.clk(serial_clk),.async_n(rst_n),.rst_n(serial_n));",
                "always @(posedge reset_clk or negedge rst_n)\n        if(!rst_n) serial_reset_pipe<=3'b111;\n        else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};").replace(
                ".RESET(!serial_n)", ".RESET(serial_reset_pipe[2])"))
        if mode == "pixel-activehigh-route1" and source.name == "a741_hdmi.v":
            target.write_text(target.read_text().replace(
                "wire pixel_n,serial_n;", "wire pixel_n; (* ASYNC_REG=\"TRUE\" *) reg [2:0] serial_reset_pipe;").replace(
                "reset_sync serial_reset(.clk(serial_clk),.async_n(rst_n),.rst_n(serial_n));",
                "always @(posedge pixel_clk or negedge rst_n)\n        if(!rst_n) serial_reset_pipe<=3'b111;\n        else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};").replace(
                ".RESET(!serial_n)", ".RESET(serial_reset_pipe[2])"))
        listing.append((target.name, "file.verilog"))
    if mode in ("pll-55-activehigh-route1", "pll-55-local-reset-route1"):
        pll = out / "gowin_pll_mod.v"
        pll.write_text(pll.read_text().replace("ODIV0_SEL = 16", "ODIV0_SEL = 15").replace(
            "ODIV0_FRAC_SEL = 4", "ODIV0_FRAC_SEL = 0"))
        hdmi = out / "a741_hdmi.v"
        hdmi.write_text(hdmi.read_text().replace("pixel_clk,serial_clk,rst_n", "pixel_clk,serial_clk,reset_clk,rst_n").replace(
            "wire pixel_n,serial_n;", "wire pixel_n; (* ASYNC_REG=\"TRUE\" *) reg [2:0] serial_reset_pipe;").replace(
            "reset_sync serial_reset(.clk(serial_clk),.async_n(rst_n),.rst_n(serial_n));",
            "always @(posedge reset_clk or negedge rst_n)\n        if(!rst_n) serial_reset_pipe<=3'b111;\n        else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};").replace(
            ".RESET(!serial_n)", ".RESET(serial_reset_pipe[2])"))
    if mode == "pll-55-local-reset-route1":
        hdmi = out / "a741_hdmi.v"
        content = hdmi.read_text()
        content = content.replace(' (* ASYNC_REG="TRUE" *) reg [2:0] serial_reset_pipe;', '')
        content = content.replace("    always @(posedge reset_clk or negedge rst_n)\n        if(!rst_n) serial_reset_pipe<=3'b111;\n        else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};", "")
        content = content.replace("        wire serial_data;", """        wire serial_data;
        (* ASYNC_REG="TRUE", syn_preserve=1, syn_keep=1 *) reg [2:0] serial_reset_pipe;
        always @(posedge reset_clk or negedge rst_n)
            if(!rst_n) serial_reset_pipe<=3'b111;
            else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};""")
        hdmi.write_text(content)
    experiment_top = top
    if mode in ("pll-div2-reset", "pll-pixel-activehigh-reset", "pll-pixel-activehigh-route1", "pll-55-activehigh-route1", "pll-55-local-reset-route1"):
        experiment_top = top.replace("wire serial_clk,pixel_clk,locked", "wire serial_clk,pixel_clk,reset_clk,locked").replace(
            ".clkout0()", ".clkout0(reset_clk)").replace(
            ".rst_n(stop_n && locked)", ".reset_clk(reset_clk),.rst_n(stop_n && locked)")
    (out / "clock_audit.v").write_text(experiment_top)
    (out / "clock_audit.cst").write_text(cst + ('CLOCK_LOC "serial_clk" LOCAL_CLOCK;\n' if mode == "serial-local" else ""))
    sdc = base_sdc + ("" if mode == "auto-derived" else generated)
    if mode == "pixel-reset-min-delay":
        # Rejected diagnostic: this tool treats the RESET min-delay as an
        # exception with no paths and removes normal recovery/removal checks.
        # Keep only to reproduce that behavior; NEVER apply to main sources.
        sdc += "set_min_delay 3.0 -from [get_pins {hdmi/pixel_reset/pipe_2_s0/Q}] -to [get_pins {hdmi/lanes*.serializer/RESET}]\n"
    if mode == "pll-div2-reset":
        sdc += "create_generated_clock -name reset82m5 -source [get_ports {clk}] -multiply_by 33 -divide_by 20 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT0}]\n"
    if mode in ("pll-pixel-activehigh-reset", "pll-pixel-activehigh-route1"):
        sdc += "create_generated_clock -name reset33m -source [get_ports {clk}] -multiply_by 33 -divide_by 50 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT0}]\n"
        sdc += "set_false_path -to [get_pins {hdmi/serial_reset_pipe*/PRESET}]\n"
    if mode == "pixel-activehigh-route1":
        sdc += "set_false_path -to [get_pins {hdmi/serial_reset_pipe*/PRESET}]\n"
    if mode in ("pll-55-activehigh-route1", "pll-55-local-reset-route1"):
        sdc += "create_generated_clock -name reset55m -source [get_ports {clk}] -multiply_by 11 -divide_by 10 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT0}]\n"
        sdc += "set_false_path -to [get_pins {hdmi/serial_reset_pipe*/PRESET}]\n"
        if mode == "pll-55-local-reset-route1":
            sdc = sdc.replace("hdmi/serial_reset_pipe*/PRESET", "hdmi/lanes*.serial_reset_pipe*/PRESET")
    (out / "clock_audit.sdc").write_text(sdc)
    listing += [("clock_audit.v", "file.verilog"), ("clock_audit.cst", "file.cst"),
                ("clock_audit.sdc", "file.sdc")]
    project = ET.Element("Project")
    ET.SubElement(project, "Template").text = "FPGA"
    ET.SubElement(project, "Version").text = "5"
    ET.SubElement(project, "Device", name="GW5AT-60B", pn="GW5AT-LV60PG484AC1/I0").text = "gw5at60b-002"
    files = ET.SubElement(project, "FileList")
    for path, kind in listing:
        ET.SubElement(files, "File", path=path, type=kind, enable="1")
    ET.ElementTree(project).write(out / "clock_audit.gprj", encoding="utf-8", xml_declaration=True)
    script = """cd [file dirname [file normalize [info script]]]
open_project clock_audit.gprj
set_option -top_module clock_audit
set_option -output_base_name clock_audit
set_option -verilog_std sysv2017
set_option -route_option 2
set_option -place_option 1
run all
"""
    if mode == "pixel-domain-reset-hold":
        script = script.replace("run all", "set_option -timing_driven 1\nset_option -correct_hold_violation 1\nrun all")
    if mode in ("pll-pixel-activehigh-route1", "pixel-activehigh-route1", "pll-55-activehigh-route1", "pll-55-local-reset-route1"):
        script = script.replace("-route_option 2", "-route_option 1")
    (out / "build.tcl").write_text(script)
    started = time.time()
    with (out / "build.log").open("w", encoding="utf-8") as log:
        try:
            rc = subprocess.run([str(GOWIN), str(out / "build.tcl")], cwd=out,
                                stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode
        except subprocess.TimeoutExpired:
            rc = -1
    report = out / "impl/pnr/clock_audit.tr"
    text = report.read_text(errors="replace") if report.is_file() else ""
    result = {"diagnostic_only": True, "hardware_programmed": False, "mode": mode,
              "returncode": rc, "seconds": time.time() - started,
              "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
              "violations": dict(re.findall(r"<Numbers of (\w+) Violated Endpoints>:(\d+)", text)),
              "mpw_section": text[text.rfind("3.2 Minimum Pulse Width Table"):text.rfind("3.3 Timing Report")],
              "experiment_source_sha256": {name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name, kind in listing}}
    if mode == "pixel-reset-min-delay":
        result["accepted_for_integration"] = False
        result["rejection_reason"] = "RESET paths disappear from recovery/removal; the min-delay exception reports no paths. Zero counts do not prove a physical fix."
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(mode, "rc", rc, "seconds", result["seconds"], result["violations"], flush=True)
    print(result["mpw_section"][:2500], flush=True)
