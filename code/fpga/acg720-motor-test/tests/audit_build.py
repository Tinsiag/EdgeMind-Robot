"""Check the actual routed motor pins and STA summary before SRAM programming."""
from pathlib import Path
import argparse
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
pnr = root / "impl/pnr"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--variant", choices=["20khz", "1khz", "start50", "toggle", "toggle80", "toggle20k80", "toggle50k80"], default="20khz")
args = parser.parse_args()
variant = args.variant
basename, user_code = {
    "20khz": ("acg720_motor_test", "0000a710"),
    "1khz": ("acg720_motor_test_1khz", "0000a711"),
    "start50": ("acg720_motor_test_start50", "0000a712"),
    "toggle": ("acg720_motor_toggle", "0000a713"),
    "toggle80": ("acg720_motor_toggle_80", "0000a714"),
    "toggle20k80": ("acg720_motor_toggle_20khz_80", "0000a715"),
    "toggle50k80": ("acg720_motor_toggle_50khz_80", "0000a716"),
}[variant]
expected = {
    "clk": ("Y18", "in"), "stop_n": ("F15", "in"),
    "left_key_n": ("A20", "in"), "right_key_n": ("B20", "in"),
    "left_in1": ("A13", "out"), "left_in2": ("A14", "out"),
    "left_enc_a": ("A15", "in"), "left_enc_b": ("A16", "in"),
    "right_in1": ("F16", "out"), "right_in2": ("E17", "out"),
    "right_enc_a": ("D20", "in"), "right_enc_b": ("C20", "in"),
    "camera_reset_n": ("C14", "out"),
}
expected.update({f"led[{i}]": (ball, "out") for i, ball in enumerate(
    ["M22", "N22", "L21", "K21", "K22", "J22", "H22", "M21"])})
report = (pnr / f"{basename}.rpt.txt").read_text(encoding="utf-8")
pin_section = report.split("7. Pinout by Port Name", 1)[1].split("8. All Package Pins", 1)[0]
pins = {}
for line in pin_section.splitlines():
    cells = [s.strip() for s in line.split("|")]
    if len(cells) < 18 or cells[0] == "Port Name":
        continue
    name = cells[0]
    assert name in expected, f"Unexpected output/input auto-placed: {name}"
    ball, direction = expected[name]
    assert cells[2].split("/")[0] == ball, (name, cells[2], ball)
    assert cells[3] == "Y" and cells[4] == direction, (name, cells[3:5])
    assert cells[7] == "LVCMOS33" and cells[17] == "3.3", (name, cells[7], cells[17])
    if name.endswith("in1") or name.endswith("in2"):
        assert cells[9] == "DOWN" and cells[8] == "4", (name, cells[8:10])
    pins[name] = {"ball": ball, "direction": direction, "io_type": cells[7]}
assert set(pins) == set(expected), "Missing routed ports"
assert "GW5AT-LV60PG484AC1/I0" in report and "<Device Version>: B" in report
timing = (pnr / f"{basename}_tr_content.html").read_text(encoding="utf-8")
violations = {}
for kind in ["Setup", "Hold"]:
    match = re.search(rf"Numbers of {kind} Violated Endpoints</td>\s*<td>(\d+)</td>", timing)
    assert match, f"Missing {kind} STA summary"
    violations[kind] = int(match[1])
    assert violations[kind] == 0, f"{kind} timing violations"
assert "50.000(MHz)" in timing, "Missing 50 MHz clock constraint"
fmax = re.search(r"<td>50\.000\(MHz\)</td>\s*<td>([\d.]+)\(MHz\)</td>", timing)
assert fmax and float(fmax[1]) >= 50
bitstream = pnr / f"{basename}.fs"
header = bitstream.open(encoding="ascii").read(1024)
assert f"//usercode: 0x{user_code}" in header.lower(), "Wrong/malformed motor test User Code"
sources = ["rtl/acg720_motor_test.v", "constraints/acg720_motor_test.cst",
           "constraints/acg720_motor_test.sdc", "acg720_motor_test.gprj", "build.tcl"]
if variant == "1khz":
    sources += ["rtl/acg720_motor_test_1khz.v", "acg720_motor_test_1khz.gprj", "build_1khz.tcl"]
elif variant == "start50":
    sources += ["rtl/acg720_motor_test_start50.v", "acg720_motor_test_start50.gprj", "build_start50.tcl"]
elif variant == "toggle":
    sources = ["rtl/acg720_motor_toggle.v", "constraints/acg720_motor_test.cst",
               "constraints/acg720_motor_test.sdc", "acg720_motor_toggle.gprj", "build_toggle.tcl"]
elif variant == "toggle80":
    sources = ["rtl/acg720_motor_toggle.v", "rtl/acg720_motor_toggle_80.v",
               "constraints/acg720_motor_test.cst", "constraints/acg720_motor_test.sdc",
               "acg720_motor_toggle_80.gprj", "build_toggle80.tcl"]
elif variant == "toggle20k80":
    sources = ["rtl/acg720_motor_toggle.v", "rtl/acg720_motor_toggle_20khz_80.v",
               "constraints/acg720_motor_test.cst", "constraints/acg720_motor_test.sdc",
               "acg720_motor_toggle_20khz_80.gprj", "build_toggle20k80.tcl"]
elif variant == "toggle50k80":
    sources = ["rtl/acg720_motor_toggle.v", "rtl/acg720_motor_toggle_50khz_80.v",
               "constraints/acg720_motor_test.cst", "constraints/acg720_motor_test.sdc",
               "acg720_motor_toggle_50khz_80.gprj", "build_toggle50k80.tcl"]
audit = {
    "device": "GW5AT-LV60PG484AC1/I0 (GW5AT-60B)", "pins": pins,
    "timing_violations": violations, "fmax_mhz": float(fmax[1]),
    "variant": variant,
    "bitstream_user_code": f"0x{user_code.upper()}",
    "bitstream_sha256": hashlib.sha256(bitstream.read_bytes()).hexdigest().upper(),
    "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest().upper()
                      for name in sources},
}
suffix = "" if variant == "20khz" else f"-{variant}"
out = root / f".local/build-audit{suffix}-20261010.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"PASS: {len(pins)} routed ports match wiring, 50 MHz setup/hold violations=0")
print(f"Actual Fmax={fmax[1]} MHz; User Code=0x{user_code.upper()}; variant={variant}")
print(f"FS SHA256={audit['bitstream_sha256']}")
