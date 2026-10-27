"""Archive existing evidence only. Never invokes EDA, hardware, or network tools."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
FUSION = ROOT / "code/camera-car-control/a741-fpga-fusion"
MOTION = ROOT / "output/motion-tft800-20261028"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot(result_path, destination, source_overrides=None):
    source_overrides = source_overrides or {}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    entries = []
    for i, (name, expected) in enumerate(result["source_sha256"].items()):
        source = Path(name)
        override = source_overrides.get(source)
        data = (override.read_bytes() if override else source.read_bytes())
        origin = ("archived platform bytes, matched against recorded build hash" if override
                  else "current bytes, matched against recorded build hash")
        if digest(data) != expected:
            # The sole change after d5 and attempts 1/2 is the experimental
            # CLOCK_LOC stanza. Recover only when the original prefix hashes
            # exactly to the pre-existing build record; never guess content.
            if source == FUSION / "constraints/board.cst" and not override:
                candidates = [data[:n] for n in range(len(data) + 1)]
                data = next((b for b in candidates if digest(b) == expected), None)
                origin = "original prefix recovered; exact recorded SHA-256 matched"
            else:
                data = None
            if data is None:
                raise RuntimeError(f"Cannot recover exact original bytes: {name}")
        relative = source.relative_to(ROOT).as_posix()
        target = destination / f"{i:04d}-{source.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError(f"Refusing to overwrite different archived evidence: {target}")
        target.write_bytes(data)
        entries.append({"original_path": name, "workspace_path": relative,
                        "file": target.name, "sha256": expected,
                        "bytes": len(data), "recovery": origin})
    write_json(destination / "SOURCE-MAP.json", {
        "recorded_result": result_path.relative_to(ROOT).as_posix(),
        "recorded_result_sha256": digest(result_path.read_bytes()),
        "all_recorded_sources_recovered_and_hash_verified": True,
        "entries": entries,
        "note": "Flat filenames avoid Windows path limits. Restore workspace_path into a separate directory; do not overwrite the current worktree. No build was run during archival."
    })
    return len(entries)


def main():
    source = FUSION / ".local/gowin-basic-tft800"
    third = MOTION / "attempt3-local-clock-pr0004"
    # Copy existing bytes only. Existing differing evidence causes failure.
    for src_root, dst_root in [(source, third),
                               (FUSION / ".local/platform-basic-tft800", third / "platform")]:
        for src in src_root.rglob("*"):
            if src.is_file():
                dst = dst_root / src.relative_to(src_root)
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists() and dst.read_bytes() != src.read_bytes():
                    raise RuntimeError(f"Archive collision: {dst}")
                shutil.copy2(src, dst)
    attempts = []
    for folder in ["attempt1-pr0004", "attempt2-pr0004", "attempt3-local-clock-pr0004"]:
        result_path = MOTION / folder / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        row = {k: result.get(k) for k in [
            "mode", "compile_passed", "returncode", "timed_out", "seconds", "run_state",
            "route_option", "place_option", "timing_driven", "correct_hold_violation",
            "cache_reuse_requested", "synthesis_reused", "tool_auto_resynthesized",
            "synthesis_netlist_sha256", "timing_signed_off"]}
        row.update({"directory": folder, "error": "ERROR (PR0004) : There are total 0 unrouted nets",
                    "bitstream_exists": bool(list((MOTION / folder).rglob("*.fs"))),
                    "final_timing_report_exists": bool(list((MOTION / folder).rglob("*.tr"))),
                    "sdf_exists": bool(list((MOTION / folder).rglob("*.sdf")))})
        overrides = {}
        if folder != "attempt3-local-clock-pr0004":
            # The result records the generated .local path, while the attempt
            # archive preserves the exact platform input used by that run.
            overrides[FUSION / ".local/platform-basic-tft800/a741.cst"] = MOTION / folder / "platform/a741.cst"
        row["archived_source_count"] = snapshot(result_path, MOTION / folder / "source-snapshot", overrides)
        attempts.append(row)
    golden = ROOT / "output/tft800-official-20261028"
    golden_count = snapshot(golden / "build-evidence-final/result.json", golden / "source-snapshot-d5")
    write_json(MOTION / "clock-routing-outcome.json", {
        "original_hypothesis_preserved": "clock-routing-hypothesis.json",
        "third_attempt": attempts[-1],
        "lidar_enable_removed_from_PRIMARY": True,
        "ui_n_promoted_to_PRIMARY": True,
        "PRIMARY_used": 8, "PRIMARY_total": 8,
        "placement_seconds_from_report": 135, "routing_seconds_from_report": 109,
        "root_cause_confirmed": False, "hypothesis_fixed_failure": False,
        "experiment_constraint_remains_in_worktree": True,
        "termination": "Tool exited with PR0004 before pause interrupt; not user-interrupted and not timeout.",
        "next_action": "Paused by user; do not retry PNR or modify constraints until resumed."
    })
    write_json(MOTION / "STATUS.json", {
        "status": "paused_by_user_after_three_PR0004_failures",
        "attempts": attempts,
        "latest_hardware_sha256": "d5e558ad68ac665f889fcec651262714e52e40774853e5368c51f0fc2a1ad62b",
        "camera_restored_user_confirmed": True,
        "cold_boot_deferred_by_user": True,
        "last_user_confirmed_hardware_conditions": {"wheels_raised": True, "motor_vm_off": True, "downloader_connected": True},
        "motion_candidate_exists": False, "motion_candidate_programmed": False,
        "arm_sent": False, "motion_performed": False,
        "review_scripts_prepared_but_not_executed": "REVIEW-SCRIPTS.json",
        "network_reply_received": False,
        "next_step": "Handoff and GitHub publication only; development/hardware remain paused."
    })
    print(json.dumps({"third_attempt_archived": True, "golden_sources_verified": golden_count,
                      "attempts": attempts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
