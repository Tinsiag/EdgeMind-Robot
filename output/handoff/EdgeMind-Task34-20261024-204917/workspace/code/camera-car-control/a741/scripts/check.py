"""Run isolated A741 RTL regression and host tests without board I/O."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
CAMERA = ROOT.parent
REPO = CAMERA.parents[1]
MOTION = CAMERA.parent / "fpga/acg720-motion-control/rtl"
VISION = CAMERA.parent / "fpga/acg720-vision-motion/rtl"


def sources():
    from vendor import checksum_source
    checksum = checksum_source(ROOT)
    return (sorted((ROOT / "rtl").glob("*.v")) +
            [p for p in sorted((CAMERA / "third_party/verilog-ethernet/rtl").glob("*.v")) if p.name != "udp_checksum_gen.v"] +
            [checksum] +
            [CAMERA / "rtl/video_udp_packetizer.v"] +
            [MOTION / n for n in ("uart_rx.v", "uart_tx.v", "quadrature_decoder.v", "encoder_counter.v")] +
            [VISION / n for n in ("motor_pwm_safe.v", "vision_packet_tx.v", "i2c_reg_master.v",
                                  "vl53l1x_driver.v", "vl53l1x_config_rom.v", "reset_sync.v",
                                  "dvp_capture_continuous.v", "capture_tokens.v", "async_fifo.v", "cdc_mailbox.v",
                                  "ddr_framebuffer.v", "video_pixels.v", "video_timing.v")])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", help="Run named RTL benches only")
    args = parser.parse_args()
    out = ROOT / ".local/tests"
    out.mkdir(parents=True, exist_ok=True)
    inputs = sources() + list((ROOT / "host").glob("*.py")) + list((ROOT / "tests").glob("*"))
    inputs += [ROOT / "config/calibration.json"]
    inputs += list((ROOT / "native").glob("*")) + list((ROOT / "third_party/coreslam").glob("*"))
    mapping_dll=ROOT / ".local/mapping/edgemind_slam.dll"
    if mapping_dll.is_file():inputs.append(mapping_dll)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    bins = REPO / "tmp/vision-motion-tools/bin"
    passed = []
    for bench in sorted((ROOT / "tests").glob("*_tb.v")):
        if args.only and bench.stem not in args.only:
            continue
        product = out / (bench.stem + ".vvp")
        extra = []
        if bench.stem == "network_tb":
            from network_check import vectors
            vector_path = out / "network-input.hex"
            count = vectors(vector_path)
            extra = [f"+INPUT={vector_path}", f"+COUNT={count}", f"+DUMP={out / 'network-output.hex'}"]
        command = [str(bins / "iverilog.exe"), "-g2012", "-Wall", "-s", bench.stem,
                   "-o", str(product), *map(str, sources()), str(bench)]
        if bench.stem == "hdmi_tb":
            command += [str(ROOT / ".local/platform/dvi_encoder.v"),
                        "C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v"]
        compile_result = subprocess.run(command, capture_output=True, text=True)
        if compile_result.returncode:
            raise RuntimeError(compile_result.stdout + compile_result.stderr)
        run = subprocess.run([str(bins / "vvp.exe"), str(product), *extra], capture_output=True, text=True, timeout=60)
        (out / (bench.stem + ".log")).write_text(run.stdout + run.stderr, encoding="utf-8")
        if run.returncode or "PASS" not in run.stdout:
            raise RuntimeError(run.stdout + run.stderr)
        print(run.stdout.strip())
        if bench.stem == "network_tb":
            from network_check import verify
            verify(out / "network-output.hex")
        passed.append(bench.stem)
    if args.only:
        return
    for top in ("a741_motion", "a741_sensors", "a741_telemetry"):
        subprocess.run([str(bins / "iverilog.exe"), "-g2012", "-Wall", "-s", top, "-o",
                        str(out / (top + ".vvp")), *map(str, sources())], check=True)
    host = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"),
                           "-p", "test_*.py", "-v"], capture_output=True, text=True)
    host_log = host.stdout+host.stderr
    (out / "host.log").write_text(host_log, encoding="utf-8")
    print(host_log)
    if host.returncode:
        raise RuntimeError("Host regression failed")
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p, h in before.items()):
        raise RuntimeError("Sources changed during regression")
    record = {"rtl_passed": passed, "hardware_tested": False, "unix_time": time.time(),
              "host_tests": int(re.search(r"Ran (\d+) tests", host_log)[1]), "input_sha256": before}
    (out / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
