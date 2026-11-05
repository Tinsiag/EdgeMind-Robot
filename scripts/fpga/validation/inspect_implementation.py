"""Read the completed build and save review evidence. Never programs hardware."""
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parents[3] / 'output/current-firmware'
OUT.mkdir(parents=True, exist_ok=True)
ROOT = OUT.parent.parent
PROJECT = ROOT / "code/camera-car-control/a745-autonomous"
BUILD = PROJECT / ".local/gowin-a745-autonomous"
PNR = BUILD / "impl/pnr"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def atomic_text(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(value, encoding='utf-8')
    temporary.replace(path)


def write(name, value):
    atomic_text(OUT / name, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def section(text, heading, next_heading):
    match = re.search(r"(?ms)^" + re.escape(heading) + r"\s*\n(.*?)(?=^" + re.escape(next_heading) + r"\s*\n)", text)
    return match[1] if match else ""


class PinRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row = []
        elif tag == "td" and self.row is not None: self.cell = []

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip()); self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row); self.row = None


def main():
    result = json.loads(read(BUILD / "result.json"))
    assert result["run_state"] != "running", "Wait for the build to finish"
    changed = [name for name, digest in result["source_sha256"].items()
               if not Path(name).is_file() or sha(Path(name)) != digest]
    assert not changed, changed
    assert not result["motor_locked"] and not result["screen_test"] and result["motion_lidar"]
    import sys
    sys.path.insert(0,str(PROJECT / "scripts"))
    from timing_report import current_report
    report_path, report = current_report(PNR,result["evidence_freshness_lower_bound_unix"])
    assert report_path is not None
    physical = read(PNR / "a745.rpt.txt") if (PNR / "a745.rpt.txt").is_file() else ""
    log = read(BUILD / "build.log")
    commands = read(PNR / "cmd.do")
    # Match the explicitly recorded options, including the validated video
    # design's place/route=2. Never report a different option as signed off.
    route, place = int(result['route_option']), int(result['place_option'])
    assert route in (1, 2) and place in (1, 2)
    options = {key: bool(re.search(pattern, commands, re.M)) for key, pattern in {
        "route_matches_build": rf"^-route_option {route}$", "place_matches_build": rf"^-place_option {place}$",
        "timing_driven": r"^-timing$", "correct_hold": r"^-correct_hold 1$"}.items()}
    assert all(options.values()), options
    if 'clock_route_order' in result:
        assert re.search(r'^-clock_route_order '+str(result['clock_route_order'])+r'$',commands,re.M)
        options['clock_route_order']=result['clock_route_order']

    timing = {"violated_endpoints": result.get("timing_violations", {}),
              "clock_frequencies": result.get("clock_frequencies", {}),
              "worst_reported_slack_ns": {}, "per_clock_tns": []}
    headings = ["3.1.1 Setup Paths Table", "3.1.2 Hold Paths Table", "3.1.3 Recovery Paths Table",
                "3.1.4 Removal Paths Table", "3.2 Minimum Pulse Width Table", "3.3 Timing Report By Analysis Type"]
    timing["empty_analysis_tables"] = []
    for i, name in enumerate(("setup", "hold", "recovery", "removal", "minimum_pulse_width")):
        body = section(report, headings[i], headings[i+1])
        values = [float(x) for x in re.findall(r"(?m)^\s*\d+\s+(-?\d+\.\d+)\s+", body)]
        timing["worst_reported_slack_ns"][name] = min(values) if values else None
        if not values and "Nothing to report!" in body:
            timing["empty_analysis_tables"].append(name)
        atomic_text(OUT / (name + "-paths.txt"), body)
    tns = section(report, "2.4 Total Negative Slack Summary", "3. Timing Details")
    for clock, analysis, slack, count in re.findall(r"(?m)^\s*(\S+)\s+(setup|hold|recovery|removal)\s+(-?\d+\.\d+)\s+(\d+)\s*$", tns):
        timing["per_clock_tns"].append({"clock": clock, "analysis": analysis, "tns_ns": float(slack), "endpoints": int(count)})
    # Keep actual exception/constraint and congestion text for human review.
    for label in ("High Fanout Nets Report", "Route Congestions Report", "Timing Constraints Report"):
        match = re.search(r"(?ms)^3\.\d+\s+" + label + r"\s*\n(.*?)(?=^3\.\d+\s|\Z)", report)
        atomic_text(OUT / (label.lower().replace(" ", "-") + ".txt"), match[1] if match else "Section not provided\n")
    expected_clocks = {"sys_clk": 50, "camera_pclk": 100, "rx125m": 125,
                       "memory400m": 400, "ddr_ui100m": 100,
                       "tx125m": 125, "display33m":33}
    actual = timing["clock_frequencies"]
    timing["expected_live_clocks"] = expected_clocks
    timing["live_clocks_match"] = set(actual) == set(expected_clocks) and all(
        abs(actual[name]["constraint_mhz"] - mhz) < 0.01 for name, mhz in expected_clocks.items())
    clock_summary = section(report, "2.2 Clock Summary", "2.3 Max Frequency Summary")
    summary_clocks = {name: float(freq) for name, freq in re.findall(
        r"(?m)^\s*\d+\s+(\S+)\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)(?:MHz)?", clock_summary)}
    # tx250m only feeds the dedicated divider, so it has no data-path Fmax.
    expected_summary = dict(expected_clocks,tx250m=250)
    timing["clock_summary"] = summary_clocks
    timing["clock_summary_matches"] = summary_clocks == expected_summary
    timing["inactive_constraints"] = [line.strip() for line in report.splitlines()
                                     if re.search(r"TC_\w+\s+(?!Actived\b)\w+\s+", line)]
    timing["numeric_checks_pass"] = bool(report) and timing["live_clocks_match"] and timing["clock_summary_matches"] and not timing["inactive_constraints"] and all(
        (v is not None and v >= 0) or (name in ("recovery", "removal") and name in timing["empty_analysis_tables"])
        for name, v in timing["worst_reported_slack_ns"].items()) and all(
        value == 0 for value in timing["violated_endpoints"].values()) and all(
        row["tns_ns"] >= 0 and row["endpoints"] == 0 for row in timing["per_clock_tns"])
    write("TIMING-REVIEW.json", timing)

    netlist_path = BUILD / "impl/gwsynthesis/a745.vg"
    netlist = read(netlist_path)
    assert sha(netlist_path) == result["synthesis_netlist_sha256"]
    locked = {}
    for pin in ("left_in1", "left_in2", "right_in1", "right_in2"):
        match = re.search(r"OBUF " + pin + r"_obuf\s*\(.*?\);", netlist, re.S)
        assert match and ".I(GND)" not in match[0] and ".I(VCC)" not in match[0], pin
        locked[pin] = match[0]
    pins = PinRows(); pins.feed(read(PNR / "a745.pin.html"))
    platform = Path(result["platform_directory"])
    expected_pins = {name: ball for name, ball in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);', read(platform / "a745.cst"))
                     if name.startswith(("left_", "right_", "imu_", "lidar_", "tft_", "rgmii_"))}
    assigned = {}
    for name, ball in expected_pins.items():
        rows = [row for row in pins.rows if len(row) > 17 and row[0] == name]
        assert len(rows) == 1 and rows[0][2].split("/")[0] == ball and rows[0][7] == "LVCMOS33", (name, rows)
        assigned[name] = rows[0]
    assert not any(row and re.match(r"(?:hdmi|tof_)", row[0]) for row in pins.rows)
    resources = []
    for line in physical.splitlines():
        match = re.match(r"\s*([\w /(),-]+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*$", line)
        if match: resources.append({"resource": match[1].strip(), "usage": match[2], "utilization": match[3]})
    write("PHYSICAL-REVIEW.json", {"resources": resources, "motor_obufs": locked,
          "pin_assignments": assigned, "cmd_do_options": options, "source_inputs_match": True,
          "netlist_sha256": sha(netlist_path), "pnr_phase_times": [line.strip() for line in physical.splitlines()
          if any(word in line for word in ("Elapsed time", "Peak memory"))]})
    write("WARNINGS.json", {"counts": dict(Counter(re.findall(r"WARN\s+\((\w+)\)", log))),
          "errors": [line for line in log.splitlines() if re.match(r"\s*(ERROR|FATAL)", line)],
          "pnr_warnings": [line for line in log.splitlines()[next((i for i,line in enumerate(log.splitlines()) if "GowinSynthesis finish" in line), 0):]
                           if re.search(r"WARN|ERROR|FATAL", line)]})
    artifact = Path(result["artifact"]) if result.get("artifact") else None
    if artifact:
        assert sha(artifact) == result["artifact_sha256"]
    # result.json contains the review pointer finalized by final_gate.py;
    # hash immutable build artifacts here and validate its fields at the gate.
    copies = [BUILD / name for name in ("build.tcl", "build.log", "a745.gprj")]
    copies += [p for p in PNR.iterdir() if p.is_file() and p.suffix not in (".pr", ".db", ".p", ".fs", ".bin", ".binx")]
    copies += [netlist_path, BUILD / "impl/gwsynthesis/a745_syn_rsc.xml", platform / "a745.cst", platform / "a745.sdc", platform / "provenance.json"]
    # Retain hashes instead of duplicating routed SDF/netlists and bitstreams.
    write("BUILD-EVIDENCE.json", {"artifact_sha256": result.get("artifact_sha256"),
          "files": {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path) for path in copies}})
    write("CANDIDATE-IMPLEMENTATION.json", {"status": "implementation_complete_pending_review" if result["compile_passed"] else "implementation_failed",
          "compile_passed": result["compile_passed"], "seconds": result["seconds"],
          "timing_numeric_checks_pass": timing["numeric_checks_pass"], "timing_signed_off": False,
          "motor_pads_grounded": False, "artifact": str(artifact) if artifact else None,
          "artifact_sha256": result.get("artifact_sha256"), "hardware_programmed": False,
          "recorded_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"compile_passed": result["compile_passed"], "seconds": result["seconds"],
                      "timing": timing, "resources": resources[:12]}, indent=2))


if __name__ == "__main__":
    main()
