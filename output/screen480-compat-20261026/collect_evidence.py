"""Record this 480-screen change without accessing or programming hardware."""
import hashlib
import json
from pathlib import Path
import re
import shutil

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PROJECT = REPO / "code/camera-car-control/a741-fpga-fusion"
REFERENCE = REPO.parent / "fpga/4.3inchTFT/demos/ac620/AC620_TFT43"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reference_files = ["rtl/TFT_CTRL_480_270_16b.v", "NIOS_TFT43.v", "mysystem.qsys",
                       "mysystem/synthesis/submodules/mysystem_altpll_0.v",
                       "NIOS_TFT43.qsf", "software/test/TFT_API.h"]
    rtl = (REFERENCE / reference_files[0]).read_text(encoding="utf-8-sig")
    values = {name: int(value) for name, value in
              re.findall(r"(TFT_[HV]S_end|[hv]dat_begin|[hv]dat_end|hpixel_end|vline_end)\s*=\s*10'd(\d+)", rtl)}
    pll = (REFERENCE / reference_files[3]).read_text(encoding="utf-8")
    def parameter(name):
        return int(re.search(r"pll7\." + name + r"\s*=\s*(\d+)", pll)[1])
    actual_hz = 10**12 / parameter("inclk0_input_frequency") * parameter("clk2_multiply_by") / parameter("clk2_divide_by")
    reference = {"project": str(REFERENCE), "sha256": {name: sha(REFERENCE / name) for name in reference_files},
                 "scan_parameters": values, "actual_pll_pixel_hz": actual_hz,
                 "comment_pixel_hz": 9000000, "reference_back_porch_pixels_lines": [1, 1],
                 "implemented_back_porch_pixels_lines": [2, 2],
                 "reason": "AT043TN24 timing table requires at least 2 clocks/lines for each back porch."}
    reference["panel_documents_sha256"] = {str(p.relative_to(REPO)): sha(p) for p in
        (REPO / "model/chassis/v5-rgb-touch-display/references").glob("*.pdf")}
    (OUT / "REFERENCE-AUDIT.json").write_text(json.dumps(reference, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tests = ["tft480_panel_tb", "tft480_timing_tb", "mission_navigation_tb", "osd_tb",
             "hdmi_tb", "video_tb", "video_capture_tb", "sensors_tb"]
    evidence = OUT / "tests"
    evidence.mkdir(exist_ok=True)
    for name in tests + ["screen480-host"]:
        path = PROJECT / ".local/tests" / (name + ".log")
        # Keep the standard check.py decoder for the WSL warning prefix.
        import sys
        sys.path.insert(0, str(PROJECT / "scripts"))
        from check import simulation_text
        log = simulation_text(path)
        if (name != "screen480-host" and "PASS" not in log) or "FATAL" in log or "Assertion failed" in log:
            raise RuntimeError("No passing evidence for " + name)
        if name == "screen480-host" and not re.search(r"Ran 61 tests.*\n\s*\nOK", log, re.S):
            raise RuntimeError("Host regression did not pass")
        (evidence / path.name).write_text(log, encoding="utf-8")
    paths = [PROJECT / "display/rtl/a741_tft480_panel.v", PROJECT / "display/tests/tft480_panel_tb.v",
             PROJECT / "display/tests/tft480_timing_tb.v", PROJECT / "rtl/a741_osd.v",
             PROJECT / "scripts/build.py", PROJECT / "scripts/check.py"]
    result = {"screen_confirmed_by_user": "480x272", "rtl_passed": tests, "host_tests_passed": 61,
              "clk_hz": 50000000, "pixel_hz": 10000000, "pixel_period_ns": 100,
              "pixel_high_low_ns": [40, 60], "rtl_setup_hold_ns": [60, 40],
              "frame_total": [525, 286], "frame_active": [480, 272],
              "frame_hz": 10000000 / (525 * 286), "backlight_frames": 11,
              "backlight_delay_ms": 11 * (525 * 286) / 10000000 * 1000,
              "source_sha256": {str(p.relative_to(REPO)): sha(p) for p in paths},
              "timing_signed_off": False, "hardware_programmed": False,
              "physical_screen_tested": False, "power_cycle_verified": False,
              "known_navigation_blocker": "Continuous obstacle scenario remains failed in the 20261025 handoff."}
    build = PROJECT / ".local/gowin-fusion-tft480"
    record = json.loads((build / "result.json").read_text(encoding="utf-8"))
    if record["run_state"] == "running":
        raise RuntimeError("Wait for synthesis to finish before collecting final evidence")
    for name in ("result.json", "build.tcl", "build.log"):
        shutil.copy2(build / name, OUT / ("synthesis-" + name))
    result["synthesis"] = {key: record.get(key) for key in
        ("compile_passed", "run_state", "seconds", "sources_changed", "route_option", "place_option",
         "synthesis_netlist_sha256", "synthesis_timing")}
    (OUT / "RESULTS.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
