"""Build isolated A741 diagnostics, optionally with MPU6050 and motor lock."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from check import CAMERA, ROOT, VISION, sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pulse_width_slack(text):
    # Anchor to the real table, not its indented table-of-contents entry.
    table = re.search(r"^3\.2 Minimum Pulse Width Table\n(.*?)^3\.3 ", text, re.M | re.S)
    if not table:
        return None
    values = re.findall(r"(?m)^\s*\d+\s+(-?\d+\.\d+)\s+", table[1])
    return min(map(float, values)) if values else None


def prepare(examples, imu_test=False, motion_lidar=False):
    out = ROOT / (".local/platform-motion-lidar" if motion_lidar else ".local/platform-imu-test" if imu_test else ".local/platform")
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
    sdc += "create_generated_clock -name memory400m -source [get_ports {clk}] -multiply_by 8 -phase 0 -duty_cycle 50 [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}]\n"
    sdc += "create_generated_clock -name ddr_ui100m -source [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}] -master_clock memory400m -divide_by 4 [get_pins {memory/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]\n"
    sdc += (ROOT / "constraints/cdc.sdc").read_text(encoding="utf-8")
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
                "ddr_ipc_sha256": hashlib.sha256(ddr_ipc_raw).hexdigest(),
                "pin_assignments": assigned,
                "adaptations": ["Rename chapter38 video PLL modules to avoid network PLL collision.",
                                "Preserve TMDS encoder; use OSER10 serializers instead of fabric modulo-5 shifters.",
                                "Model pixel CLKDIV from the implemented video PLL output at divide-by-5.",
                                "Model DDR UI clock from the memory PLL at divide-by-4, matching original IPC 400 MHz/1:4.",
                                "Define static 0-degree/50-percent PLL parent clocks before CLKDIV constraints; dynamic DDR calibration still requires review.",
                                "DDR mDRP bypass released after 16 locked cycles, per verified project correction."]}
    (out / "provenance.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    top = (ROOT / "rtl/a741_top.v").read_text(encoding="utf-8")
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
    parser.add_argument("--examples", type=Path, default=Path("C:/Users/Administrator/Documents/ACG720-GW5AT60K例程文件/GW5AT60K"))
    parser.add_argument("--gowin", default="C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe")
    args = parser.parse_args()
    if args.imu_test and args.motion_lidar:
        parser.error("Choose exactly one hardware variant")
    build_folder = "gowin-motion-lidar" if args.motion_lidar else "gowin-imu-test" if args.imu_test else "gowin-board"
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
    files, platform = prepare(args.examples, args.imu_test, args.motion_lidar)
    if args.mode == "prepare":
        print("Prepared A741 platform; IMU test="+str(args.imu_test)+"; no hardware operation.")
        return
    out = ROOT / ".local" / ((build_folder+"-synth") if args.mode == "synth" else build_folder)
    out.mkdir(parents=True, exist_ok=True)
    listing = [(p, "file.verilog") for p in files]
    listing += [(platform / "a741.cst", "file.cst"), (platform / "a741.sdc", "file.sdc")]
    hashes = {str(p): sha(p) for p, _ in listing}
    if args.imu_test or args.motion_lidar:
        for path in (ROOT / "config/sensor-pins.json", ROOT / "scripts/build.py"):
            hashes[str(path)] = sha(path)
    reused_netlist = None
    if args.mode == "pnr":
        previous = json.loads((out / "result.json").read_text(encoding="utf-8"))
        netlist = out / "impl/gwsynthesis/a741.vg"
        previous_log = (out / "build.log").read_text(encoding="utf-8", errors="replace")
        if previous["sources_changed"] or not netlist.is_file():
            raise RuntimeError("PNR requires an unchanged, completed synthesis")
        for name, expected in hashes.items():
            if Path(name).suffix.lower() == ".v" and previous["source_sha256"].get(name) != expected:
                raise RuntimeError("RTL changed; run a complete build before PNR: "+name)
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
        + ("run syn\n" if args.mode == "synth" else "run pnr\n" if args.mode == "pnr" else "run all\n"))
    if args.mode == "pnr":
        previous_tcl = (out / "build.tcl").read_text(encoding="utf-8")
        if previous_tcl.rsplit("\nrun ", 1)[0] != tcl.rsplit("\nrun ", 1)[0]:
            raise RuntimeError("Synthesis options changed; run a complete build")
    (out / "build.tcl").write_text(tcl, encoding="utf-8")
    started = time.time()
    timed_out = False
    with (out / "build.log").open("w", encoding="utf-8") as log:
        try:
            run = subprocess.run([args.gowin, str(out / "build.tcl")], cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            rc = run.returncode
        except subprocess.TimeoutExpired:
            timed_out, rc = True, -1
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
    if netlist.is_file():
        record["synthesis_netlist_sha256"] = sha(netlist)
        if reused_netlist is not None and record["synthesis_netlist_sha256"] != reused_netlist:
            passed = False
            record["compile_passed"] = False
    record["calibration_json_sha256"] = sha(ROOT / "config/calibration.json")
    if passed:
        record.update(artifact=str(artifact), artifact_sha256=sha(artifact))
    (out / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(("PASS" if passed else "FAIL") + ": A741 " + args.mode + "; IMU test="+str(args.imu_test)+"; timing NOT signed off")
    print(out / "build.log")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
