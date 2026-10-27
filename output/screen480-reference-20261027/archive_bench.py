"""Freeze and inspect the explicitly selected motor-locked 480-screen image."""
import hashlib
import json
from pathlib import Path
import re
import shutil

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PROJECT = REPO / "code/camera-car-control/a741-fpga-fusion"
BUILD = PROJECT / ".local/gowin-fusion-tft480-screen-test"
ARCHIVE = OUT / "bench-image-20261027"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads((BUILD / "result.json").read_text(encoding="utf-8"))
    tested=json.loads((OUT/"TEST-RESULT.json").read_text(encoding="utf-8"))
    for name,expected in tested["input_sha256"].items():
        if sha(Path(name))!=expected:
            raise RuntimeError("Tested inputs changed: "+name)
    power=json.loads((OUT/"POWER-CONFIRMATION.json").read_text(encoding="utf-8"))
    if not power["motor_vm_off"] or not power["logic_screen_programmer_powered"]:
        raise RuntimeError("Current bench power confirmation missing")
    if record.get("run_state") != "completed" or not record.get("compile_passed"):
        raise RuntimeError("The selected complete build has not succeeded")
    if not record.get("screen_test") or not record.get("motor_locked"):
        raise RuntimeError("This is not a hard-locked screen experiment")
    if record.get("route_option") != 1 or record.get("place_option") != 1:
        raise RuntimeError("Unexpected place/route algorithm")
    changed = [name for name, expected in record["source_sha256"].items()
               if not Path(name).is_file() or sha(Path(name)) != expected]
    if changed:
        raise RuntimeError("Compiler inputs changed: " + repr(changed))
    netlist = BUILD / "impl/gwsynthesis/a741.vg"
    if sha(netlist) != record["synthesis_netlist_sha256"]:
        raise RuntimeError("Synthesis netlist changed")
    raw = netlist.read_text(encoding="utf-8")
    top = re.search(r"module\s+a741_top\s*\(.*?\bendmodule\b", raw, re.S)[0]
    if not re.search(r"\bGND\s+\S+\s*\(\s*\.G\(GND\)\s*\)", top, re.S):
        raise RuntimeError("Top-level ground driver missing")
    motors = {}
    for signal in ("left_in1", "left_in2", "right_in1", "right_in2"):
        cells = re.findall(r"\bOBUF\s+(\S+)\s*\((.*?)\);", top, re.S)
        connected = [(name, pins) for name, pins in cells
                     if re.search(r"\.O\(\s*" + signal + r"\s*\)", pins)]
        if len(connected) != 1 or not re.search(r"\.I\(\s*GND\s*\)", connected[0][1]):
            raise RuntimeError("Motor output not directly grounded in netlist: " + signal)
        motors[signal] = {"cell": connected[0][0], "input": "GND"}
    command = (BUILD / "impl/pnr/cmd.do").read_text(encoding="utf-8")
    for option in (r"(?m)^-route_option\s+1\s*$", r"(?m)^-place_option\s+1\s*$",
                   r"(?m)^-timing\s*$", r"(?m)^-correct_hold\s+1\s*$"):
        if not re.search(option, command):
            raise RuntimeError("Final cmd.do option missing: " + option)
    image = BUILD / "impl/pnr/a741.fs"
    if Path(record["artifact"]).resolve() != image.resolve() or sha(image) != record["artifact_sha256"]:
        raise RuntimeError("Bitstream does not match the complete build")
    ARCHIVE.mkdir(exist_ok=True)
    target = ARCHIVE / "A741-TFT480-AC620-5MHZ-SCREEN-TEST-MOTOR-LOCKED-20261027.fs"
    if target.exists() and sha(target) != record["artifact_sha256"]:
        raise RuntimeError("Keep existing archive: same name has a different image")
    shutil.copy2(image, target)
    files = {"result.json": "result.json", "build.tcl": "build.tcl", "build.log": "build.log",
             "impl/pnr/cmd.do": "cmd.do", "impl/pnr/a741.tr": "a741.tr",
             "impl/pnr/a741.pin.html": "a741.pin.html",
             "impl/gwsynthesis/a741_syn.rpt.html": "a741_syn.rpt.html"}
    for source, name in files.items():
        shutil.copy2(BUILD / source, ARCHIVE / name)
    audit = {"purpose": "User-authorized 480x272 screen bench experiment; no motion release",
             "user_confirmed_vm_off_and_logic_cable_powered": True,
             "power_confirmation":power,"screen_reference":"AC620_TFT43 actual5MHz, DE42/11",
             "rtl_passed":tested["rtl_passed"],"host_tests_passed":tested["host_tests_passed"],
             "bitstream": str(target.resolve()), "sha256": sha(target),
             "compiler_inputs_verified": len(record["source_sha256"]),
             "netlist_sha256": sha(netlist), "motor_output_buffers": motors,
             "route_option": 1, "place_option": 1, "timing_driven": True, "correct_hold": True,
             "timing_signed_off": False, "motion_release_allowed": False,
             "hardware_programmed": False, "cold_boot_verified": False,
             "timing_violations": record.get("timing_violations"),
             "worst_reported_slack_ns": record.get("worst_reported_slack_ns"),
             "minimum_pulse_width_worst_slack_ns": record.get("minimum_pulse_width_worst_slack_ns")}
    (ARCHIVE / "BENCH-IDENTITY.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
