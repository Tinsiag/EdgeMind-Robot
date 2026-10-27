"""Run isolated A741 RTL regression and host tests without board I/O."""
from pathlib import Path
import argparse
import os
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
PRIMITIVES = Path(os.environ.get("GOWIN_SIMLIB", "C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v"))


def bench_sources(bench):
    if bench.stem == "tft800_reference_tb":
        return [ROOT / "display/reference/acg720-ch28/disp_driver.v"]
    if bench.stem == "ethernet_io_tb":
        return [CAMERA / "rtl/acg720_rgmii_rx.v", PRIMITIVES]
    return []


def simulation_text(path):
    data=path.read_bytes()
    # wsl.exe may prefix Linux UTF-8 stdout with one Windows UTF-16 warning.
    if data.startswith(b"w\x00s\x00l\x00:"):
        end=data.find(b"\n\x00")
        if end>=0:
            return data[:end+2].decode("utf-16-le",errors="replace")+data[end+2:].decode("utf-8",errors="replace")
    return data.decode("utf-8",errors="replace")


def sources():
    from vendor import checksum_source
    checksum = checksum_source(ROOT)
    return (sorted((ROOT / "rtl").glob("*.v")) + sorted((ROOT / "display/rtl").glob("*.v")) + [ROOT / "third_party/picorv32/picorv32.v"] +
            [p for p in sorted((CAMERA / "third_party/verilog-ethernet/rtl").glob("*.v")) if p.name != "udp_checksum_gen.v"] +
            [checksum] +
            [MOTION / n for n in ("uart_rx.v", "quadrature_decoder.v", "encoder_counter.v")] +
            [VISION / n for n in ("motor_pwm_safe.v", "reset_sync.v",
                                  "dvp_capture_continuous.v", "capture_tokens.v", "async_fifo.v", "cdc_mailbox.v",
                                  "ddr_framebuffer.v", "video_pixels.v")])


def rtl_benches():
    return sorted([*(ROOT/"tests").glob("*_tb.v"),*(ROOT/"display/tests").glob("*_tb.v"),
                   VISION.parent/"tests/ddr_framebuffer_tb.v"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", help="Run named RTL benches only")
    parser.add_argument("--wsl", metavar="DISTRO", help="Run installed Icarus/VVP inside this WSL distro; host tests still use this Python")
    args = parser.parse_args()
    benches=rtl_benches()
    available={p.stem for p in benches}
    if args.only and not set(args.only)<=available:
        parser.error("Unknown RTL bench: "+", ".join(sorted(set(args.only)-available)))
    out = ROOT / ".local/tests"
    out.mkdir(parents=True, exist_ok=True)
    inputs = sources() + list((ROOT / "host").glob("*.py")) + list((ROOT / "tests").glob("*"))+benches
    inputs += [ROOT / "config/calibration.json"]
    inputs += [ROOT / "config/geometry.json"]+list((ROOT / "scripts").glob("*.py"))
    inputs += list((ROOT / "firmware").glob("*")) + [ROOT / "third_party/picorv32/source.json"]
    inputs += list((ROOT / "display/reference").glob("*.v"))
    inputs += list((ROOT / "display/reference/acg720-ch28").glob("*.v"))
    inputs += list((ROOT / "tests/reference").glob("*.v"))
    inputs += [p for bench in benches for p in bench_sources(bench)]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    bins = REPO / "tmp/vision-motion-tools/bin"
    def path_arg(path):
        value=Path(path).resolve().as_posix()
        return "/mnt/"+value[0].lower()+value[2:] if args.wsl else value
    def command(tool,arguments):
        return (["wsl.exe","-d",args.wsl,"--cd",path_arg(ROOT),"--exec",tool,*arguments] if args.wsl else
                [str(bins/(tool+".exe")),*arguments])
    passed = []
    backends={}
    for bench in benches:
        if args.only and bench.stem not in args.only:
            continue
        product = out / (bench.stem + ".vvp")
        extra = []
        if bench.stem in ("network_tb",):
            from importlib import import_module
            network=import_module("network_check")
            vector_path = out / (bench.stem+"-input.hex")
            count = network.vectors(vector_path)
            extra = [f"+INPUT={path_arg(vector_path)}", f"+COUNT={count}", f"+DUMP={path_arg(out / (bench.stem+'-output.hex'))}"]
        compile_args = ["-g2012", "-Wall", "-s", bench.stem,
                   "-o", path_arg(product), *map(path_arg, sources()+bench_sources(bench)), path_arg(bench)]
        if bench.stem=="tft480_reference_tb":
            compile_args += [path_arg(ROOT/"display/reference/TFT_CTRL_480_270_16b.v")]
        include_args=["-I"+path_arg(ROOT/"display/reference/acg720-ch28")] if bench.stem=="tft800_reference_tb" else []
        compile_args+=include_args
        if args.wsl and bench.stem in ("camera_tft_tb", "tft480_timing_tb", "tft480_reference_tb", "display_diagnostic_tb", "phy_powerup_tb", "camera_tft800_tb", "display800_diagnostic_tb", "tft800_reference_tb"):
            # Compile the full camera/display fixture and long panel timing tests.
            # The LCD startup/reset test also runs 18 complete physical frames.
            obj="/var/tmp/edgemind-"+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]+"-"+bench.stem
            compile_cmd=command("verilator",["--binary","--timing","-j","4","-Wno-fatal","--Mdir",obj,
                "--top-module",bench.stem,*include_args,*map(path_arg,sources()+bench_sources(bench)),path_arg(bench),
                *([path_arg(ROOT/"display/reference/TFT_CTRL_480_270_16b.v")] if bench.stem=="tft480_reference_tb" else [])])
            run_cmd=command(obj+"/V"+bench.stem,[])
            backends[bench.stem]="verilator"
        else:
            compile_cmd=command("iverilog",compile_args)
            run_cmd=command("vvp",[path_arg(product),*extra])
            backends[bench.stem]="icarus"
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True, errors="replace",cwd=ROOT)
        (out/(bench.stem+"-compile.log")).write_text(compile_result.stdout+compile_result.stderr,encoding="utf-8")
        if compile_result.returncode:
            raise RuntimeError(compile_result.stdout + compile_result.stderr)
        log_path=out/(bench.stem+".log")
        with log_path.open("w",encoding="utf-8") as simulation_log:
            run = subprocess.run(run_cmd,cwd=ROOT,stdout=simulation_log,stderr=subprocess.STDOUT,
                timeout=60)
        run_log=simulation_text(log_path)
        log_path.write_text(run_log,encoding="utf-8")
        if run.returncode or "PASS" not in run_log:
            raise RuntimeError(run_log)
        print(run_log.strip())
        if bench.stem in ("network_tb",):
            network.verify(out / (bench.stem+"-output.hex"))
        passed.append(bench.stem)
    if args.only:
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in before.items()):
            raise RuntimeError("Sources changed during selected regression")
        record={"rtl_passed":passed,"full_suite":False,"hardware_tested":False,"unix_time":time.time(),
                "rtl_backend_per_bench":backends,"input_sha256":before}
        (out/"selection-result.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
        return
    for top in ("a741_motion", "a741_sensors", "a741_telemetry"):
        subprocess.run(command("iverilog",["-g2012", "-Wall", "-s", top, "-o",
                        path_arg(out / (top + ".vvp")), *map(path_arg, sources())]), check=True,cwd=ROOT)
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
              "rtl_backend":"wsl:"+args.wsl if args.wsl else "windows-icarus",
              "rtl_backend_per_bench":backends,
              "host_tests": int(re.search(r"Ran (\d+) tests", host_log)[1]), "input_sha256": before}
    (out / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
