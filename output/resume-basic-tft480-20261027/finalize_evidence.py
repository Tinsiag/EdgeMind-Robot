"""Archive this completed offline run; never invokes build, PNR, or hardware tools."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from zipfile import ZipFile

OUT = Path(__file__).resolve().parent
REPO = OUT.parent.parent
PROJECT = REPO / "code/camera-car-control/a741-fpga-fusion"
BUILD = PROJECT / ".local/gowin-basic-tft480-screen-test-synth"
SYN = BUILD / "impl/gwsynthesis"
HANDOFF = REPO / "output/handoff-basic-tft480-20261027"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def audit_inputs(inputs):
    missing = [name for name in inputs if not Path(name).is_file()]
    changed = [name for name, digest in inputs.items() if Path(name).is_file() and sha(Path(name)) != digest]
    return {"inputs": len(inputs), "missing": missing, "changed": changed, "all_match": not missing and not changed}


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    assert sha(source) == sha(target), target


def main():
    tests = read(PROJECT / ".local/tests/result.json")
    build = read(BUILD / "result.json")
    resources = read(OUT / "resources.json")
    assert build["compile_passed"] and not build["sources_changed"] and build["mode"] == "synth"
    assert build["motor_locked"] and not build["hardware_programmed"]
    assert not list(BUILD.rglob("*.fs")) and not (BUILD / "impl/pnr").exists()
    assert sha(SYN / "a741.vg") == build["synthesis_netlist_sha256"]
    assert resources["evidence_sha256"][str(BUILD / "result.json")] == sha(BUILD / "result.json")
    audit = {"regression": audit_inputs(tests["input_sha256"]),
             "synthesis": audit_inputs(build["source_sha256"])}
    assert audit["regression"]["all_match"] and audit["synthesis"]["all_match"], audit

    netlist = (SYN / "a741.vg").read_text(encoding="utf-8")
    obufs = {}
    for pin in ("left_in1", "left_in2", "right_in1", "right_in2"):
        match = re.search(r"OBUF " + pin + r"_obuf\s*\(.*?\);", netlist, re.S)
        assert match and re.search(r"\.I\(GND\)", match[0]), pin
        obufs[pin] = match[0]
    audit["screen_test_pads"] = {"all_four_grounded": True, "netlist_sha256": sha(SYN / "a741.vg"), "obufs": obufs}
    platform = Path(build["platform_directory"])
    provenance = read(platform / "provenance.json")
    assert sha(Path(provenance["chapter38"])) == provenance["chapter38_sha256"]
    vendor = {}
    with ZipFile(provenance["chapter38"]) as archive:
        for name, recorded in provenance["files"].items():
            original = hashlib.sha256(archive.read(name)).hexdigest()
            actual = sha(platform / Path(name).name)
            assert actual == original == recorded["original_sha256"] == recorded["sha256"], name
            vendor[name] = {"original_sha256": original, "sha256": actual}
    audit["vendor_ddr_ip"] = {"all_original_hashes_match": True, "files": vendor}
    cst = sha(platform / "a741.cst")
    expected_cst = "9c9bd84a476a77c1ac6b1a5e54cd88ed74b9227aad9d3b3d292f5285b04f0c93"
    assert cst == expected_cst
    audit["generated_constraints"] = {"cst_sha256": cst, "matches_handoff_prepared_cst": True,
                                      "sdc_sha256": sha(platform / "a741.sdc")}
    clocks = build["synthesis_timing"]["clocks"]
    audit["synthesis_clock_names"] = [clock["clock"] for clock in clocks]
    assert len(clocks) == 6 and not any("hdmi" in clock["clock"].lower() for clock in clocks)
    tcl = (BUILD / "build.tcl").read_text(encoding="utf-8")
    options = {key: int(re.search(r"set_option -" + key + r" (\d+)", tcl)[1])
               for key in ("route_option", "place_option", "timing_driven", "correct_hold_violation")}
    assert set(options.values()) == {1} and re.search(r"^run syn$", tcl, re.M)
    audit["tcl_options"] = {**options, "run": "syn", "actual_pnr_cmd_do": "not generated: PNR not run"}
    audit.update(pnr_performed=False, hardware_programmed=False)
    write("FINAL-INPUT-AUDIT.json", audit)

    log = (BUILD / "build.log").read_text(encoding="utf-8", errors="replace")
    counts = Counter(re.findall(r"WARN\s+\((\w+)\)", log))
    errors = len(re.findall(r"ERROR\s+\(", log))
    assert errors == 0
    write("warnings.json", {"counts": dict(counts), "total": sum(counts.values()), "errors": errors,
          "inferred_latch_warning": "EX2420 checksum_part[31] in generated UDP checksum adapter; final utilization reports zero register-as-latch",
          "undriven_ports": "Mostly disabled PTP/pause/control side channels in vendor Ethernet and unused PicoRV32 PCPI outputs; not warning-free",
          "reviewed_as_not_timing_signoff": True, "build_log_sha256": sha(BUILD / "build.log")})

    for name in ("result.json", "build.log", "build-timeline.jsonl", "build.tcl", "a741.gprj"):
        copy(BUILD / name, OUT / "synthesis" / name)
    for path in SYN.iterdir():
        if path.is_file():
            copy(path, OUT / "synthesis" / path.name)
    for name in ("a741.cst", "a741.sdc", "provenance.json", "basic-parameters.json"):
        copy(platform / name, OUT / "synthesis" / name)
    copy(PROJECT / ".local/tests/result.json", OUT / "regression-result.json")
    for bench in tests["rtl_passed"]:
        for suffix in (".log", "-compile.log"):
            copy(PROJECT / ".local/tests" / (bench + suffix), OUT / "tests" / (bench + suffix))
    for name in ("host.log", "network_tb-input.hex", "network_tb-output.hex", "camera-tft.ppm"):
        copy(PROJECT / ".local/tests" / name, OUT / "tests" / name)
    from PIL import Image
    with Image.open(OUT / "tests/camera-tft.ppm") as picture:
        picture.save(OUT / "camera-tft-simulation.png")
    write("camera-tft-simulation.json", {"synthetic_test_pattern": True, "hardware_image": False,
          "source": "tests/camera-tft.ppm", "source_sha256": sha(OUT / "tests/camera-tft.ppm"),
          "regression_result_sha256": sha(OUT / "regression-result.json")})

    original = read(HANDOFF / "SOURCE-MANIFEST.json")
    changes = []
    snapshot_paths = set()
    for entry in original["current_source"]:
        path = REPO / entry["path"]
        if path.is_file():
            snapshot_paths.add(path)
        current = sha(path) if path.is_file() else None
        if current != entry["sha256"]:
            changes.append({"path": entry["path"], "status": "modified" if current else "deleted",
                            "handoff_sha256": entry["sha256"], "sha256": current})
    for name in ("RESUME-20261027.md", "code/camera-car-control/a741-fpga-fusion/scripts/report_resources.py",
                 "code/camera-car-control/a741-fpga-fusion/tests/basic_safety_tb.v",
                 "code/camera-car-control/a741-fpga-fusion/tests/ld06_orientation_tb.v"):
        assert not (HANDOFF / "current-source" / name).exists(), name
        path = REPO / name
        changes.append({"path": name, "status": "added_after_handoff", "sha256": sha(path)})
        snapshot_paths.add(path)
    deleted_still_absent = [name for name in original["deleted_tracked_files"] if not (REPO / name).exists()]
    assert len(deleted_still_absent) == len(original["deleted_tracked_files"])
    write("CHANGES-FROM-HANDOFF.json", {"base_commit": original["base_commit"],
          "comparison": "original 120-file handoff manifest plus explicitly added source/entry files; generated evidence excluded",
          "deleted_handoff_files_still_absent": len(deleted_still_absent), "changes": changes})
    snapshot_paths.update(Path(name) for name in tests["input_sha256"])
    snapshot_paths.update(Path(name) for name in build["source_sha256"])
    snapshot = []
    for path in sorted(snapshot_paths):
        relative = path.relative_to(REPO)
        copy(path, OUT / "source-snapshot" / relative)
        snapshot.append({"path": relative.as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    write("SOURCE-SNAPSHOT.json", {"base_commit": original["base_commit"], "files": snapshot,
          "scope": "recorded test/build inputs, handoff current-source files and newly added sources; not a portable toolchain bundle"})

    before_fix = read(OUT / "before-lidar-orientation-fix/resources.json")
    write("ORIENTATION-FIX-COMPARISON.json", {
        "comparison": {key: {"before_fix": before_fix["comparison"][key]["after"],
                             "after_fix": value["after"],
                             "delta": value["after"] - before_fix["comparison"][key]["after"]}
                       for key, value in resources["comparison"].items()},
        "note": "Two distinct frozen whole-board synthesis runs; small mapped-resource changes outside edited modules may reflect optimization variability. No PNR."})
    status = {"status": "offline_implementation_regression_and_synthesis_complete",
              "rtl_tests": len(tests["rtl_passed"]), "python_tests": tests["host_tests"],
              "all_current_inputs_match": True, "regression_inputs": audit["regression"]["inputs"],
              "synthesis_inputs": audit["synthesis"]["inputs"], "new_basic_synthesis_completed": True,
              "synthesis_seconds": build["seconds"],
              "resources": {**{name: resources["comparison"][key]["after"] for name, key in
                                (("lut", "T_Lut"), ("register", "T_Register"), ("alu", "T_Alu"), ("bsram", "T_Bsram"))}, "actual_cls": None},
              "system_fmax_synthesis_estimate_mhz": next(clock["estimated_fmax_mhz"] for clock in clocks if clock["clock"] == "clk"),
              "ddr_cross_clock_synthesis_slack_ns": min(path["slack_ns"] for path in build["synthesis_timing"]["paths"]),
              "full_board_pnr_started": False, "final_timing_signed_off": False,
              "new_bitstream_generated": False, "hardware_programmed": False, "cold_boot_verified": False,
              "screen_test_motor_pads_grounded": True, "motion_release_allowed": False,
              "github_uploaded": False, "telemetry_local_experiment_merged": False,
              "lidar_orientation_fix_included": True, "recorded_utc": datetime.now(timezone.utc).isoformat()}
    write("STATUS.json", status)
    print(json.dumps({"status": status, "source_snapshot_files": len(snapshot), "changed_files": len(changes)}, indent=2))


if __name__ == "__main__":
    main()
