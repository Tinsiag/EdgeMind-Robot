"""Read the completed build and save review evidence. Never programs hardware."""
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
PROJECT = ROOT / "code/camera-car-control/a741-fpga-fusion"
BUILD = PROJECT / ".local/gowin-basic-tft480-screen-test"
PNR = BUILD / "impl/pnr"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    report = read(PNR / "a741.tr") if (PNR / "a741.tr").is_file() else ""
    physical = read(PNR / "a741.rpt.txt") if (PNR / "a741.rpt.txt").is_file() else ""
    log = read(BUILD / "build.log")
    commands = read(PNR / "cmd.do")
    options = {key: bool(re.search(pattern, commands, re.M)) for key, pattern in {
        "route_1": r"^-route_option 1$", "place_1": r"^-place_option 1$",
        "timing_driven": r"^-timing$", "correct_hold": r"^-correct_hold 1$"}.items()}
    assert all(options.values()), options

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
        (OUT / (name + "-paths.txt")).write_text(body, encoding="utf-8")
    tns = section(report, "2.4 Total Negative Slack Summary", "3. Timing Details")
    for clock, analysis, slack, count in re.findall(r"(?m)^\s*(\S+)\s+(setup|hold|recovery|removal)\s+(-?\d+\.\d+)\s+(\d+)\s*$", tns):
        timing["per_clock_tns"].append({"clock": clock, "analysis": analysis, "tns_ns": float(slack), "endpoints": int(count)})
    # Keep actual exception/constraint and congestion text for human review.
    for label in ("High Fanout Nets Report", "Route Congestions Report", "Timing Constraints Report"):
        match = re.search(r"(?ms)^3\.\d+\s+" + label + r"\s*\n(.*?)(?=^3\.\d+\s|\Z)", report)
        (OUT / (label.lower().replace(" ", "-") + ".txt")).write_text(match[1] if match else "Section not provided\n", encoding="utf-8")
    expected_clocks = {"sys_clk": 50, "camera_pclk": 100, "rgmii_rx_clk": 125,
                       "memory400m": 400, "ddr_ui100m": 100,
                       "tx125m": 125}
    actual = timing["clock_frequencies"]
    timing["expected_live_clocks"] = expected_clocks
    timing["live_clocks_match"] = set(actual) == set(expected_clocks) and all(
        abs(actual[name]["constraint_mhz"] - mhz) < 0.01 for name, mhz in expected_clocks.items())
    clock_summary = section(report, "2.2 Clock Summary", "2.3 Max Frequency Summary")
    summary_clocks = {name: float(freq) for name, freq in re.findall(
        r"(?m)^\s*\d+\s+(\S+)\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)MHz", clock_summary)}
    expected_summary = {**expected_clocks, "tx250m": 250}
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

    netlist_path = BUILD / "impl/gwsynthesis/a741.vg"
    netlist = read(netlist_path)
    assert sha(netlist_path) == result["synthesis_netlist_sha256"]
    locked = {}
    for pin in ("left_in1", "left_in2", "right_in1", "right_in2"):
        match = re.search(r"OBUF " + pin + r"_obuf\s*\(.*?\);", netlist, re.S)
        assert match and ".I(GND)" in match[0], pin
        locked[pin] = match[0]
    pins = PinRows(); pins.feed(read(PNR / "a741.pin.html"))
    platform = Path(result["platform_directory"])
    expected_pins = {name: ball for name, ball in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);', read(platform / "a741.cst"))
                     if name.startswith(("left_", "right_", "imu_", "lidar_", "tft_"))}
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
    copies = [BUILD / name for name in ("result.json", "build.tcl", "build.log", "build-timeline.jsonl", "a741.gprj")]
    copies += [p for p in PNR.iterdir() if p.is_file() and p.suffix not in (".pr", ".db", ".p")]
    copies += [netlist_path, BUILD / "impl/gwsynthesis/a741_syn_rsc.xml", platform / "a741.cst", platform / "a741.sdc", platform / "provenance.json"]
    for path in copies:
        target = OUT / "build-evidence-final" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)
        assert sha(target) == sha(path)
    write("STATUS.json", {"status": "implementation_complete_pending_review" if result["compile_passed"] else "implementation_failed",
          "compile_passed": result["compile_passed"], "seconds": result["seconds"],
          "timing_numeric_checks_pass": timing["numeric_checks_pass"], "timing_signed_off": False,
          "motor_pads_grounded": True, "artifact": str(artifact) if artifact else None,
          "artifact_sha256": result.get("artifact_sha256"), "hardware_programmed": False,
          "recorded_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"compile_passed": result["compile_passed"], "seconds": result["seconds"],
                      "timing": timing, "resources": resources[:12]}, indent=2))


if __name__ == "__main__":
    main()
