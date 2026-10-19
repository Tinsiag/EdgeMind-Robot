"""Audit the closed-loop Gowin outputs for wiring revision 2026-10-14.

Report values are tool configuration, not measured board voltages. This checks
neither electrical safety nor the correctness of the motion-control algorithms.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASENAME = "acg720_motion_control"
EXPECTED = {
    "clk": ("Y18", "in"), "stop_n": ("F15", "in"),
    "uart_rx": ("J21", "in"), "uart_tx": ("M15", "out"),
    "left_in1": ("A18", "out"), "left_in2": ("A19", "out"),
    "left_enc_a": ("A15", "in"), "left_enc_b": ("A16", "in"),
    "right_in1": ("F13", "out"), "right_in2": ("F14", "out"),
    "right_enc_a": ("E13", "in"), "right_enc_b": ("E14", "in"),
}
EXPECTED.update({f"led[{i}]": (ball, "out") for i, ball in enumerate(
    ["M22", "N22", "L21", "K21", "K22", "J22", "H22", "M21"])})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_reports(report, timing, header, user_code="A720"):
    require("GW5AT-LV60PG484AC1/I0" in report and
            "<Device Version>: B" in report, "Wrong device in PnR report")
    require("7. Pinout by Port Name" in report and "8. All Package Pins" in report,
            "Missing routed pin table")
    section = report.split("7. Pinout by Port Name", 1)[1].split("8. All Package Pins", 1)[0]
    pins = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 18 or cells[0] == "Port Name":
            continue
        name = cells[0]
        require(name in EXPECTED and name not in pins, f"Unexpected/duplicate port: {name}")
        ball, bank = cells[2].split("/")
        require((ball, cells[4]) == EXPECTED[name], f"Wrong pin/direction: {name}: {cells[2]} {cells[4]}")
        require(cells[3] == "Y", f"Unconstrained port: {name}")
        require(cells[7] == "LVCMOS33" and cells[17] == "3.3", f"Wrong IO configuration: {name}")
        if name.startswith(("left_", "right_")):
            require(cells[9] == "DOWN", f"Missing motor/encoder pull-down: {name}")
        if name.endswith(("in1", "in2")):
            require(cells[8] == "4", f"Wrong motor output drive: {name}")
        pins[name] = {"ball": ball, "bank": int(bank), "direction": cells[4],
                      "io_type": cells[7], "configured_bank_vccio": cells[17]}
    require(set(pins) == set(EXPECTED), "Missing routed ports")
    require(len({p["ball"] for p in pins.values()}) == len(pins), "Duplicate routed ball")
    violations = {}
    for kind in ("Setup", "Hold"):
        match = re.search(rf"Numbers of {kind} Violated Endpoints</td>\s*<td>(\d+)</td>", timing)
        require(match is not None, f"Missing {kind} timing summary")
        violations[kind] = int(match[1])
        require(violations[kind] == 0, f"{kind} timing violations: {violations[kind]}")
    fmax = re.search(r"<td>sys_clk</td>\s*<td>50\.000\(MHz\)</td>\s*<td>([\d.]+)\(MHz\)</td>", timing)
    require(fmax is not None and float(fmax[1]) >= 50, "Missing/failed 50 MHz Fmax")
    slacks = {}
    for kind in ("Setup", "Hold"):
        section = re.search(rf'<a name="{kind}_Slack_Table">.*?</table>', timing, re.S)
        require(section is not None, f"Missing {kind} slack table")
        values = re.findall(r"<tr>\s*<td>\d+</td>\s*<td>(-?[\d.]+)</td>", section[0])
        require(bool(values), f"Missing {kind} path slacks")
        slacks[kind] = min(map(float, values))
        require(slacks[kind] >= 0, f"Negative {kind} slack")
    require(f"//usercode: 0x0000{user_code.lower()}" in header.lower(), "Wrong/missing bitstream User Code")
    require("//Part Number: GW5AT-LV60PG484AC1/I0" in header, "Wrong bitstream part")
    return {"pins": pins, "timing_violations": violations,
            "fmax_mhz": float(fmax[1]), "worst_reported_slack_ns": slacks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pnr-dir", type=Path, default=ROOT / "impl/pnr")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/build-audit-wiring-20261014.json")
    parser.add_argument("--variant", choices=("default", "start50", "ready", "sync"), default="default")
    args = parser.parse_args()
    basename, user_code, build_script = {
        "default": (BASENAME, "A720", "build.tcl"),
        "start50": ("acg720_motion_start50", "A721", "build_start50.tcl"),
        "ready": ("acg720_motion_ready", "A722", "build_ready.tcl"),
        "sync": ("acg720_motion_sync", "A723", "build_sync.tcl"),
    }[args.variant]
    try:
        bitstream = args.pnr_dir / f"{basename}.fs"
        with bitstream.open(encoding="ascii") as stream:
            header = stream.read(2048)
        result = check_reports(
            (args.pnr_dir / f"{basename}.rpt.txt").read_text(),
            (args.pnr_dir / f"{basename}_tr_content.html").read_text(), header, user_code)
        require(bitstream.stat().st_size > 2048, "Empty/truncated bitstream")
        project = ROOT / f"{basename}.gprj"
        sources = [f.attrib["path"] for f in ET.parse(project).findall(".//File")]
        sources += [project.name, build_script]
        result.update({"wiring_revision": "2026-10-14", "electrical_safety_verified": False,
                       "hardware_tested": False, "bitstream_user_code": f"0x0000{user_code}",
                       "bitstream_sha256": hashlib.sha256(bitstream.read_bytes()).hexdigest(),
                       "source_sha256_at_audit": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                                  for name in sources}})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"PASS: {len(result['pins'])} routed ports; setup/hold violations=0; Fmax={result['fmax_mhz']} MHz")
    print(f"FS SHA256: {result['bitstream_sha256']}")
    print(f"Audit: {args.output}")
    print("Report audit only; board voltages, electrical safety and hardware behavior are unverified.")


if __name__ == "__main__":
    main()
