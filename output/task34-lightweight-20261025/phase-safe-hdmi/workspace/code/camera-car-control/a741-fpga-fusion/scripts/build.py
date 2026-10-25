"""Build isolated A741 diagnostics, optionally with MPU6050 and motor lock."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from check import CAMERA, ROOT, VISION, sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthesis_timing(path):
    """Extract pre-route estimates, never treat them as timing sign-off."""
    data=path.read_text(encoding="utf-8",errors="replace")
    def rows(block):
        return [[html.unescape(re.sub(r"<[^>]*>","",cell)).replace("\xa0"," ").strip()
                 for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",row,re.S)]
                for row in re.findall(r"<tr>(.*?)</tr>",block,re.S)]
    table=re.search(r'<a name="performance">.*?<table[^>]*>(.*?)</table>',data,re.S)
    if not table:
        raise RuntimeError("Synthesis frequency table is missing")
    clocks=[]
    for row in rows(table[1])[1:]:
        if len(row)==6:
            clocks.append({"clock":row[1],"requested_mhz":float(row[2].split("(")[0]),
                "estimated_fmax_mhz":float(row[3].split("(")[0]),"logic_levels":int(row[4])})
    paths=[]
    for block in re.split(r"<h3>Path&nbsp\d+</h3>",data)[1:]:
        tables=re.findall(r"<table[^>]*>(.*?)</table>",block,re.S)
        info=dict(row for row in rows(tables[0]) if len(row)==2)
        stats=dict(row for row in rows(tables[-1]) if len(row)==2)
        paths.append({"source":info["From"],"destination":info["To"],
            "launch_clock":info["Launch Clk"],"latch_clock":info["Latch Clk"],
            "slack_ns":float(info["Slack"]),"logic_levels":int(stats["Logic Level:"])})
    return {"synthesis_estimate_only":True,"clocks":clocks,"paths":paths}


def pulse_width_slack(text):
    # Anchor to the real table, not its indented table-of-contents entry.
    table = re.search(r"^3\.2 Minimum Pulse Width Table\n(.*?)^3\.3 ", text, re.M | re.S)
    if not table:
        return None
    values = re.findall(r"(?m)^\s*\d+\s+(-?\d+\.\d+)\s+", table[1])
    return min(map(float, values)) if values else None


def prepare(examples, imu_test=False, motion_lidar=False, fusion=False, tft480=False):
    out = ROOT / (".local/platform-tft480" if tft480 else ".local/platform-motion-lidar" if motion_lidar else ".local/platform-imu-test" if imu_test else ".local/platform")
    out.mkdir(parents=True, exist_ok=True)
    platform = CAMERA / ".local/platform"
    if not (platform / "manifest.json").is_file():
        subprocess.run([sys.executable, str(CAMERA / "scripts/prepare_platform.py"),
                        "--examples", str(examples)], check=True)
    archive = next(examples.glob("第38章*/*.zip"))
    chapter47 = next(examples.glob("第47章*/*.zip"))
    entries = ["src/ddr3_memory_interface/ddr3_memory_interface.v",
               "src/ddr_pll/ddr_pll.v", "src/ddr_pll/ddr_pll_mod.v",
               "src/pll_mDRP_intf.v", "src/dvi_encoder.v",
               "src/gowin_pll/gowin_pll.v", "src/gowin_pll/gowin_pll_mod.v"]
    files, record = [], {}
    with ZipFile(archive) as z:
        ddr_ipc_raw = z.read("src/ddr3_memory_interface/ddr3_memory_interface.ipc")
        for name in entries:
            raw = z.read(name)
            data = raw
            if "/gowin_pll/" in name:
                data = raw.replace(b"Gowin_PLL", b"A741_Video_PLL")
                if name.endswith("gowin_pll_mod.v"):
                    # Keep 165 MHz TMDS and divide-by-5 pixel clocks unchanged.
                    # Previously unused CLKOUT0 supplies a 55 MHz reset clock.
                    for old, new in ((b"ODIV0_SEL = 16", b"ODIV0_SEL = 15"),
                                     (b"ODIV0_FRAC_SEL = 4", b"ODIV0_FRAC_SEL = 0")):
                        if data.count(old) != 1:
                            raise RuntimeError("Unexpected video PLL divider configuration")
                        data = data.replace(old, new)
            if name == "src/dvi_encoder.v":
                text = raw.decode("utf-8").replace("\r\n", "\n")
                begin = text.index("module encode(")
                end = text.index("module serdes_4b_10to1(")
                original_dir = out / "original"
                original_dir.mkdir(exist_ok=True)
                (original_dir / "dvi_encoder.v").write_bytes(raw)
                data = text[begin:end].replace("module encode(", "module a741_tmds_encode(").replace("`D", "").encode("utf-8")
            dest = out / Path(name).name
            dest.write_bytes(data)
            files.append(dest)
            record[name] = {"original_sha256": hashlib.sha256(raw).hexdigest(), "sha256": sha(dest)}
    cst = (CAMERA / "constraints/acg720_camera_car.cst").read_text(encoding="utf-8")
    with ZipFile(chapter47) as z:
        vendor = z.read("src/ov5640_ddr3_hdmi.cst").decode("utf-8-sig")
    cst += "\n" + "\n".join(line for line in vendor.splitlines()
                             if re.match(r'IO_(LOC|PORT) "(O_ddr_|IO_ddr_)', line))
    for signal, balls in (("tmds_clk_p", "K4,J4"), ("tmds_data_p[0]", "L3,K3"),
                          ("tmds_data_p[1]", "L5,L4"), ("tmds_data_p[2]", "M3,M2")):
        cst += f'\nIO_LOC "{signal}" {balls};\nIO_PORT "{signal}" IO_TYPE=LVCMOS33D PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;\n'
    if imu_test or motion_lidar:
        pins = json.loads((ROOT / "config/sensor-pins.json").read_text(encoding="utf-8"))
        expected = {"scl": "L18", "sda": "M20", "xda": "A1", "xcl": "B2", "ad0": "M17", "int": "B1"}
        if any(pins["mpu6050"][name]["ball"] != ball for name, ball in expected.items()):
            raise RuntimeError("IMU test wiring differs from the user's confirmed mapping")
        for name, ball in expected.items():
            cst += f'\nIO_LOC "imu_{name}" {ball};\nIO_PORT "imu_{name}" IO_TYPE=LVCMOS33 PULL_MODE=NONE BANK_VCCIO=3.3;\n'
    if motion_lidar:
        for name, ball in (("lidar_control", "H20"), ("lidar_rx", "H14")):
            cst += f'\nIO_LOC "{name}" {ball};\nIO_PORT "{name}" IO_TYPE=LVCMOS33 PULL_MODE=NONE BANK_VCCIO=3.3;\n'
    if tft480:
        screen_pins = {"tft_clk":"AB20", "tft_de":"AB22", "tft_hsync":"V19",
                       "tft_vsync":"Y19", "tft_bl":"AB21"}
        for bit, ball in enumerate(("R18","R14","P14","U18","U17","N13","R16","P15","P17","N17","T18","L6","N15","R17","P16","N14")):
            screen_pins[f"tft_rgb[{bit}]"]=ball
        for signal,ball in screen_pins.items():
            cst += f'\nIO_LOC "{signal}" {ball};\nIO_PORT "{signal}" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;\n'
    if fusion:
        cst += "\n" + (ROOT / "constraints/board.cst").read_text(encoding="utf-8")
    assigned = {}
    for signal, balls in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);', cst):
        for ball in balls.split(","):
            if ball in assigned:
                raise ValueError(f"Pin conflict {ball}: {signal}/{assigned[ball]}")
            assigned[ball] = signal
    # The test maps only MPU6050. LD06/ToF remain absent; input-only auxiliary pins never drive.
    (out / "a741.cst").write_text(cst, encoding="utf-8")
    sdc = (CAMERA / "constraints/acg720_camera_car.sdc").read_text(encoding="utf-8")
    # Gowin creates its implicit PLL clocks after SDC parsing. Define the static
    # parents first so CLKDIV sources resolve; values match the original IPCs.
    sdc += "\ncreate_generated_clock -name video165m -source [get_ports {clk}] -multiply_by 33 -divide_by 10 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}]\n"
    sdc += "create_generated_clock -name pixel33m -source [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}] -master_clock video165m -divide_by 5 [get_pins {pixel_divider/CLKOUT}]\n"
    sdc += "create_generated_clock -name hdmi_reset55m -source [get_ports {clk}] -multiply_by 11 -divide_by 10 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT0}]\n"
    # Only asynchronous assertion at the reset synchronizer is excepted.
    # Its synchronous output to OSER10 RESET remains fully timed.
    sdc += "set_false_path -to [get_pins {hdmi/lanes*.serial_reset_pipe*/PRESET}]\n"
    sdc += "create_generated_clock -name memory400m -source [get_ports {clk}] -multiply_by 8 -phase 0 -duty_cycle 50 [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}]\n"
    sdc += "create_generated_clock -name ddr_ui100m -source [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}] -master_clock memory400m -divide_by 4 [get_pins {memory/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]\n"
    sdc += (ROOT / "constraints/cdc.sdc").read_text(encoding="utf-8")
    if tft480:
        # All LCD outputs are sys_clk registers; minimum PCLK half-period is 40ns.
        # Bound output routing to 10ns, leaving margin for the panel's 10ns setup.
        sdc += '\nset_max_delay 10.000 -to [get_ports {tft_clk tft_de tft_hsync tft_vsync tft_bl tft_rgb[*]}]\n'
    if imu_test or motion_lidar:
        # Asynchronous I2C feedback enters two-stage input synchronizers.
        sdc += '\nset_false_path -from [get_ports {imu_sda imu_scl}] -to [get_pins {core/sensors/imu_bus/sda_sync_0_s0/D core/sensors/imu_bus/scl_sync_0_s0/D}]\n'
    if motion_lidar:
        sdc += '\nset_false_path -from [get_ports {lidar_rx}] -to [get_pins {core/sensors/lu/sync_0_s0/D}]\n'
    (out / "a741.sdc").write_text(sdc, encoding="utf-8")
    extra = [p for p in platform.glob("original/ch59/**/*.v")]
    extra += [platform / "ov5640_init_table_rgb.v", CAMERA / "rtl/ov5640_board_init.v",
              CAMERA / "rtl/acg720_rgmii_rx.v",
              CAMERA.parent / "fpga/acg720-ddr3/rtl/camera_init/ov5640_ctrl.v",
              CAMERA.parent / "fpga/acg720-ddr3/rtl/camera_init/sccb_master.v",
              CAMERA / "rtl/video_udp_packetizer.v"]
    extra += [VISION / n for n in ("reset_sync.v", "dvp_capture_continuous.v", "capture_tokens.v", "async_fifo.v",
                                  "cdc_mailbox.v", "ddr_framebuffer.v", "video_pixels.v", "video_timing.v")]
    manifest = {"chapter38": str(archive), "chapter38_sha256": sha(archive),
                "chapter47": str(chapter47), "chapter47_sha256": sha(chapter47),
                "files": record, "p4_enabled": False, "imu_enabled": imu_test or motion_lidar,
                "motor_locked": imu_test, "motion_lidar": motion_lidar, "tof_enabled": False,
                "tft480_enabled":tft480,
                "ddr_ipc_sha256": hashlib.sha256(ddr_ipc_raw).hexdigest(),
                "pin_assignments": assigned,
                "adaptations": ["Rename chapter38 video PLL modules to avoid network PLL collision.",
                                "Preserve TMDS encoder; use OSER10 serializers instead of fabric modulo-5 shifters.",
                                "Use previously unused video PLL CLKOUT0 at 33 MHz for serializer reset; retain recovery/removal checks.",
                                "Model pixel CLKDIV from the implemented video PLL output at divide-by-5.",
                                "Model DDR UI clock from the memory PLL at divide-by-4, matching original IPC 400 MHz/1:4.",
                                "Define static 0-degree/50-percent PLL parent clocks before CLKDIV constraints; dynamic DDR calibration still requires review.",
                                "DDR mDRP bypass released after 16 locked cycles, per verified project correction."]}
    (out / "provenance.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    top = (ROOT / "rtl/a741_top.v").read_text(encoding="utf-8")
    if tft480:
        top=top.replace("module a741_top(", "module a741_top(\n    output wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl,\n    output wire [15:0] tft_rgb,")
        top=top.replace("endmodule", "a741_tft480_panel status_panel(.clk(clk),.rst_n(control_n),.snapshot(snapshot),\n"
                        ".fusion_snapshot(fusion_snapshot),.tft_clk(tft_clk),.tft_de(tft_de),.tft_hsync(tft_hsync),\n"
                        ".tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));\nendmodule")
    if fusion:
        geometry=json.loads((ROOT / "config/geometry.json").read_text(encoding="utf-8"))
        sys.path.insert(0,str(ROOT / "host"))
        from fusion_config import compiled_parameters
        values,config_crc=compiled_parameters(geometry,json.loads((ROOT / "config/calibration.json").read_text(encoding="utf-8")))
        parameters="defparam core.FUSION_ENABLED=1;\ndefparam video.FUSION_ENABLED=1;\n"
        parameters+="".join(f"defparam core.{k}={v};\n" for k,v in values.items())
        parameters+=f"defparam core.FUSION_CONFIG_CRC=32'h{config_crc:08x};\n"
        (out / "fusion-parameters.json").write_text(json.dumps({"parameters":values,"crc32":config_crc},indent=2),encoding="utf-8")
        top=top.replace("endmodule",parameters+"endmodule")
    if motion_lidar:
        top = "`define A741_MOTION_LIDAR\n" + top
    elif imu_test:
        top = "`define A741_IMU_TEST\n" + top
    (out / "a741_top.v").write_text(top, encoding="utf-8")
    base_sources = [p for p in sources() if p.name != "a741_top.v"]
    return list(dict.fromkeys(base_sources+files+extra+[out / "a741_top.v"])), out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "synth", "build", "pnr", "report"))
    parser.add_argument("--imu-test", action="store_true", help="Enable MPU6050 only; hard-disable motor outputs")
    parser.add_argument("--motion-lidar", action="store_true", help="Enable motors, IMU and LD06 H20/H14; ToF absent")
    parser.add_argument("--fusion", action="store_true", help="Enable board-domain fusion/navigation RTL; geometry safety lock remains enforced")
    parser.add_argument("--tft480", action="store_true", help="Enable confirmed J1/FPC 4.3-inch 480x272 RGB status panel; requires --fusion")
    parser.add_argument("--in-place", action="store_true", help="Synthesize in the normal build directory to permit checked PNR reuse")
    parser.add_argument("--timeout", type=int, default=5400, help="Gowin tool wall-time limit in seconds")
    parser.add_argument("--route-option", type=int, choices=(0,1,2), default=0, help="Documented Gowin routing algorithm; 2 favors compilation speed")
    parser.add_argument("--place-option", type=int, choices=(0,1,2,3,4), default=0, help="Documented Gowin placement algorithm; 1 prioritizes routability")
    parser.add_argument("--examples", type=Path, default=Path("C:/Users/Administrator/Documents/ACG720-GW5AT60K例程文件/GW5AT60K"))
    parser.add_argument("--gowin", default="C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe")
    args = parser.parse_args()
    if args.in_place and args.mode!="synth":
        parser.error("--in-place is only valid with synth")
    if args.tft480 and not args.fusion:
        parser.error("--tft480 requires --fusion")
    if args.timeout<1:
        parser.error("--timeout must be positive")
    if args.fusion:
        from build_mission import build as build_mission
        build_mission()
    if args.fusion:
        args.motion_lidar=True
    if args.imu_test and args.motion_lidar:
        parser.error("Choose exactly one hardware variant")
    build_folder = "gowin-fusion-tft480" if args.tft480 else "gowin-fusion" if args.fusion else "gowin-motion-lidar" if args.motion_lidar else "gowin-imu-test" if args.imu_test else "gowin-board"
    if args.mode == "report":
        out = ROOT / ".local" / build_folder
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        if not result["compile_passed"] or result["sources_changed"]:
            raise RuntimeError("Report refresh requires a successful unchanged toolflow")
        for name, expected in result["source_sha256"].items():
            if sha(Path(name)) != expected:
                raise RuntimeError("Report refresh rejected: changed compiler input "+name)
        if sha(Path(result["artifact"])) != result["artifact_sha256"]:
            raise RuntimeError("Report refresh rejected: changed bitstream")
        report = out / "impl/pnr/a741.tr"
        if result.get("timing_report_sha256") and sha(report) != result["timing_report_sha256"]:
            raise RuntimeError("Report refresh rejected: changed timing report")
        result["minimum_pulse_width_worst_slack_ns"] = pulse_width_slack(report.read_text(encoding="utf-8"))
        result["timing_report_sha256"] = sha(report)
        result["summary_refreshed_unix"] = time.time()
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Timing summary refreshed; bitstream and timing sign-off status unchanged")
        return
    files, platform = prepare(args.examples, args.imu_test, args.motion_lidar,args.fusion,args.tft480)
    if args.mode == "prepare":
        print("Prepared A741 platform; IMU test="+str(args.imu_test)+"; no hardware operation.")
        return
    out = ROOT / ".local" / ((build_folder+"-synth") if args.mode == "synth" and not args.in_place else build_folder)
    out.mkdir(parents=True, exist_ok=True)
    if args.fusion:
        (out / "firmware").mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "firmware/mission.hex", out / "firmware/mission.hex")
    listing = [(p, "file.verilog") for p in files]
    listing += [(platform / "a741.cst", "file.cst"), (platform / "a741.sdc", "file.sdc")]
    hashes = {str(p): sha(p) for p, _ in listing}
    for path in (ROOT/"scripts/check.py",ROOT/"scripts/vendor.py",ROOT/"constraints/cdc.sdc",
                 CAMERA/"constraints/acg720_camera_car.cst",CAMERA/"constraints/acg720_camera_car.sdc"):
        hashes[str(path)]=sha(path)
    if args.imu_test or args.motion_lidar:
        for path in (ROOT / "config/sensor-pins.json", ROOT / "scripts/build.py"):
            hashes[str(path)] = sha(path)
    if args.fusion:
        hashes[str(ROOT / "constraints/board.cst")]=sha(ROOT / "constraints/board.cst")
        hashes[str(ROOT / "config/geometry.json")]=sha(ROOT / "config/geometry.json")
        hashes[str(ROOT / "config/calibration.json")]=sha(ROOT / "config/calibration.json")
        hashes[str(ROOT / "host/fusion_config.py")]=sha(ROOT / "host/fusion_config.py")
        for path in (ROOT / "firmware").iterdir():
            if path.is_file(): hashes[str(path)]=sha(path)
        hashes[str(out / "firmware/mission.hex")]=sha(out / "firmware/mission.hex")
    reused_netlist = None
    if args.mode == "pnr":
        previous = json.loads((out / "result.json").read_text(encoding="utf-8"))
        netlist = out / "impl/gwsynthesis/a741.vg"
        previous_log = (out / "build.log").read_text(encoding="utf-8", errors="replace")
        if previous["sources_changed"] or not netlist.is_file():
            raise RuntimeError("PNR requires an unchanged, completed synthesis")
        def synthesis_inputs(values):
            # Pin/timing files and PNR algorithm options can change at PNR.
            # Firmware initialization and every other synthesis input must match.
            return {p:h for p,h in values.items() if Path(p).suffix.lower() not in (".cst",".sdc") and
                    Path(p)!=ROOT/"scripts/build.py"}
        if synthesis_inputs(hashes)!=synthesis_inputs(previous["source_sha256"]):
            raise RuntimeError("Synthesis inputs changed (including firmware initialization); run a complete build before PNR")
        reused_netlist = sha(netlist)
        if previous.get("synthesis_netlist_sha256"):
            if reused_netlist != previous["synthesis_netlist_sha256"]:
                raise RuntimeError("Cached synthesis netlist hash mismatch")
        else:
            earliest = (out / "result.json").stat().st_mtime-previous["seconds"]-5
            if "GowinSynthesis finish" not in previous_log or netlist.stat().st_mtime < earliest:
                raise RuntimeError("No fresh completed synthesis in previous build")
    project = ET.Element("Project")
    ET.SubElement(project, "Template").text = "FPGA"
    ET.SubElement(project, "Version").text = "5"
    ET.SubElement(project, "Device", name="GW5AT-60B", pn="GW5AT-LV60PG484AC1/I0").text = "gw5at60b-002"
    filelist = ET.SubElement(project, "FileList")
    for p, kind in listing:
        ET.SubElement(filelist, "File", path=p.as_posix(), type=kind, enable="1")
    ET.ElementTree(project).write(out / "a741.gprj", encoding="utf-8", xml_declaration=True)
    tcl = (
        "cd [file dirname [file normalize [info script]]]\nopen_project a741.gprj\n"
        "set_option -top_module a741_top\nset_option -output_base_name a741\n"
        "set_option -verilog_std sysv2017\nset_option -use_sspi_as_gpio 1\n"
        "set_option -use_cpu_as_gpio 1\nset_option -user_code 0000A741\nset_option -bit_security 0\n"
        + f"set_option -route_option {args.route_option}\n"
        + f"set_option -place_option {args.place_option}\n"
        + ("run syn\n" if args.mode == "synth" else "run pnr\n" if args.mode == "pnr" else "run all\n"))
    if args.mode == "pnr":
        previous_tcl = (out / "build.tcl").read_text(encoding="utf-8")
        def synthesis_options(script):
            return re.sub(r"(?m)^set_option -(route_option|place_option) \d+\n?", "",script.rsplit("\nrun ",1)[0])
        if synthesis_options(previous_tcl)!=synthesis_options(tcl):
            raise RuntimeError("Synthesis options changed; run a complete build")
    (out / "build.tcl").write_text(tcl, encoding="utf-8")
    started = time.time()
    timed_out = False
    interrupted = False
    # Save the inputs before launching the tool. An interrupted session must not
    # leave a previous run's completed result looking like the current build.
    (out / "result.json").write_text(json.dumps({
        "variant":"A741-FPGA-FUSION-TFT480" if args.tft480 else build_folder,
        "mode":args.mode,"run_state":"running","pid":os.getpid(),"started_unix":started,
        "compile_passed":False,"seconds":0,"timed_out":False,"sources_changed":False,
        "hardware_programmed":False,"timing_signed_off":False,"route_option":args.route_option,
        "place_option":args.place_option,
        "platform_directory":str(platform),"source_sha256":hashes},indent=2),encoding="utf-8")
    with (out / "build.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen([args.gowin, str(out / "build.tcl")], cwd=out, stdout=log, stderr=subprocess.STDOUT) as tool:
            try:
                rc=tool.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                tool.kill();tool.wait();timed_out,rc=True,-1
            except KeyboardInterrupt:
                tool.terminate();tool.wait();interrupted,rc=True,130
    log = (out / "build.log").read_text(encoding="utf-8", errors="replace")
    artifact = out / ("impl/gwsynthesis/a741.vg" if args.mode == "synth" else "impl/pnr/a741.fs")
    changed = any(sha(Path(p)) != h for p, h in hashes.items())
    passed = (rc == 0 and not changed and artifact.is_file() and artifact.stat().st_mtime >= started
              and not re.search(r"(?m)^\s*(ERROR|FATAL)", log))
    timing = out / "impl/pnr/a741.tr"
    violations = {}
    worst = {}
    frequencies = {}
    pulse_width = None
    if timing.is_file() and timing.stat().st_mtime >= started:
        timing_text = timing.read_text(encoding="utf-8", errors="replace")
        frequency_table = re.search(r"2\.3 Max Frequency Summary\n(.*?)\n2\.4", timing_text, re.S)
        if frequency_table:
            for clock, requested, actual in re.findall(
                    r"(?m)^\s*\d+\s+(\S+)\s+(\d+\.\d+)\(MHz\)\s+(\d+\.\d+)\(MHz\)", frequency_table[1]):
                frequencies[clock] = {"constraint_mhz": float(requested), "reported_fmax_mhz": float(actual)}
        pulse_width = pulse_width_slack(timing_text)
        violations = {k.lower(): int(v) for k, v in re.findall(r"<Numbers of (Setup|Hold|Recovery|Removal) Violated Endpoints>:(\d+)",
                                                              timing_text)}
        for analysis in ("Setup", "Hold", "Recovery", "Removal"):
            match = re.search(analysis+r" Paths Table\n<Report Command>:[^\n]*\n(.*?)(?=\n3\.)", timing_text, re.S)
            if match:
                slacks = re.findall(r"(?m)^\s*\d+\s+(-?\d+\.\d+)\s+", match[1])
                if slacks:
                    worst[analysis.lower()] = min(map(float, slacks))
    record = {"variant": "A741-MOTION-LD06-H20-H14" if args.motion_lidar else "A741-MPU6050-6500-IMU-TEST-MOTOR-LOCKED" if args.imu_test else "A741-MPU6050-diagnostic-P4-disabled", "mode": args.mode, "compile_passed": bool(passed),
              "returncode": rc, "timed_out": timed_out, "seconds": time.time()-started,
              "run_state":"interrupted" if interrupted else "timed_out" if timed_out else "completed" if passed else "failed",
              "started_unix":started,"route_option":args.route_option,
              "place_option":args.place_option,
              "p4_enabled": False, "imu_enabled": args.imu_test or args.motion_lidar, "motor_locked": args.imu_test,
              "motion_lidar": args.motion_lidar, "tof_enabled": False,
              "platform_directory": str(platform),
              "hardware_programmed": False, "timing_signed_off": False,
              "timing_violations": violations, "sources_changed": changed, "source_sha256": hashes}
    record["worst_reported_slack_ns"] = worst
    record["clock_frequencies"] = frequencies
    record["minimum_pulse_width_worst_slack_ns"] = pulse_width
    if timing.is_file() and timing.stat().st_mtime >= started:
        record["timing_report_sha256"] = sha(timing)
    netlist = out / "impl/gwsynthesis/a741.vg"
    record["synthesis_reused"] = reused_netlist is not None
    if netlist.is_file() and (reused_netlist is not None or netlist.stat().st_mtime>=started):
        record["synthesis_netlist_sha256"] = sha(netlist)
        if reused_netlist is not None and record["synthesis_netlist_sha256"] != reused_netlist:
            passed = False
            record["compile_passed"] = False
    synth_report=out/"impl/gwsynthesis/a741_syn.rpt.html"
    if synth_report.is_file() and (synth_report.stat().st_mtime>=started or reused_netlist is not None):
        record["synthesis_timing"]=synthesis_timing(synth_report)
        record["synthesis_report_sha256"]=sha(synth_report)
    record["calibration_json_sha256"] = sha(ROOT / "config/calibration.json")
    record["fusion_enabled"]=args.fusion
    record["tft480_enabled"]=args.tft480
    if args.fusion:
        record["variant"]="A741-FPGA-FUSION-TFT480" if args.tft480 else "A741-FPGA-FUSION"
        record["geometry_verified"]=json.loads((ROOT / "config/geometry.json").read_text(encoding="utf-8")).get("navigation_geometry_verified") is True
        record["motion_release_allowed"]=False
    if passed:
        record.update(artifact=str(artifact), artifact_sha256=sha(artifact))
    (out / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(("PASS" if passed else "FAIL") + ": A741 " + args.mode + "; IMU test="+str(args.imu_test)+"; timing NOT signed off")
    print(out / "build.log")
    for clock in record.get("synthesis_timing",{}).get("clocks",[]):
        if clock["clock"]=="clk":
            print(f"Pre-route sys estimate: {clock['estimated_fmax_mhz']:.3f} MHz / {clock['requested_mhz']:.3f} MHz; {clock['logic_levels']} logic levels")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
