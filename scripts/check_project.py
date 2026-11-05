"""Check maintained documentation and local firmware evidence without hardware I/O."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "code/camera-car-control/a745-autonomous"
CURRENT = ROOT / "output/current-firmware"
BUILD = PROJECT / ".local/gowin-a745-autonomous"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def maintained_docs() -> list[Path]:
    paths = {ROOT / "README.md", ROOT / "AGENTS.md", CURRENT / "README.md"}
    for folder in ["docs", "doc", "model", "pcb", "scripts/fpga", "code"]:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            if any(part in {".venv", ".local", "__pycache__", "vendor", "node_modules"}
                   for part in path.relative_to(base).parts):
                continue
            paths.add(path)
    return sorted(paths)


def main() -> int:
    failures: list[str] = []
    counts = {"markdown_files": 0, "local_links": 0, "source_hashes": 0,
              "receipt_hashes": 0, "python_entrypoints": 0, "retained_assets": 0}

    def require(condition: bool, description: str) -> None:
        if not condition:
            failures.append(description)

    documents = maintained_docs()
    for path in documents:
        counts["markdown_files"] += 1
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        content = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$", "", content)
        for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^)\n]+)\s*\)", content):
            target = match[1].strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            else:
                target = re.sub(r'\s+[\"\'][^\"\']*[\"\']$', "", target)
            if not target or target.startswith("#") or urlsplit(target).scheme:
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            counts["local_links"] += 1
            require((path.parent / target).exists(),
                    f"Broken link in {path.relative_to(ROOT)}: {target}")
        for command_path in re.findall(r"(?:scripts|code)/[\w./-]+\.py\b", content):
            require((ROOT / command_path).is_file(),
                    f"Missing command in {path.relative_to(ROOT)}: {command_path}")

    try:
        status = load(CURRENT / "STATUS.json")
        build = load(BUILD / "result.json")
        audit = load(ROOT / status["flash_audit"])
        candidate = load(CURRENT / f'CANDIDATE-{status["firmware_revision"]}.json')
        fs = Path(status["artifact"])
        if not fs.is_absolute():
            fs = ROOT / fs
        expected = status["artifact_sha256"]
        require(digest(fs) == expected == build["artifact_sha256"] == audit["sha256"]
                == candidate["artifact_sha256"], "Current FS/build/Flash/candidate SHA mismatch")
        require(build["compile_passed"] and build["timing_signed_off"]
                and not build["sources_changed"] and build["run_state"] == "completed",
                "Current build is not signed off")
        require(all(value == 0 for value in build["timing_violations"].values())
                and not build["path_slack_violations"], "Build has timing violations")
        for field in ["flash_program_verify_completed", "reload_command_completed",
                      "status_read_completed", "configuration_ready", "user_code_verified"]:
            require(audit[field] is True, f"Flash audit incomplete: {field}")
        for name, expected_hash in build["source_sha256"].items():
            require(digest(Path(name)) == expected_hash, f"Build source changed: {name}")
            counts["source_hashes"] += 1

        benches = {p.stem for p in (PROJECT / "tests").glob("*_tb.v")}
        receipts = ["result", "protocol-result", "cpu-gate-result", "turn-geometry-result",
                    "navigation-gate-result", "lidar-replay-result", "detection-result",
                    "detection-gate-result", "mission-gate-result", "path-geometry-result"]
        for name in receipts:
            receipt = load(CURRENT / f"tests-{name}.json")
            require(bool(receipt["passed"]), f"Failed receipt: {name}")
            if name == "result":
                require(set(receipt["passed"]) == benches, "RTL bench set changed")
            if "main_netlist_sha256" in receipt:
                require(receipt["main_netlist_sha256"] == build["synthesis_netlist_sha256"],
                        f"Main netlist mismatch: {name}")
            for input_name, expected_hash in receipt["input_sha256"].items():
                require(digest(Path(input_name)) == expected_hash,
                        f"Receipt input changed in {name}: {input_name}")
                counts["receipt_hashes"] += 1

        for name in ["TFT-PAD-TIMING", "TX-SKEW-REVIEW", "RX-INPUT-REVIEW",
                     "CAMERA-INPUT-REVIEW", "DISPLAY-ISOLATION"]:
            review = load(CURRENT / f"{name}.json")
            require(review["passed"] and review["bitstream_sha256"] == expected,
                    f"Implementation audit failed or stale: {name}")
        manifest = load(CURRENT / "BUILD-EVIDENCE.json")
        require(manifest["artifact_sha256"] == expected, "Build manifest SHA mismatch")
        for name, expected_hash in manifest["files"].items():
            require(digest(ROOT / name) == expected_hash, f"Build artifact changed: {name}")
            counts["receipt_hashes"] += 1
        for field in ["flash_audit", "mode1_passive_evidence", "application_review",
                      "startup_err0011_evidence"]:
            require((ROOT / status[field]).is_file(), f"Missing current evidence: {field}")
    except (OSError, KeyError, ValueError, TypeError) as exc:
        failures.append(f"Firmware evidence: {exc}")

    entrypoints = [ROOT / "scripts/check_project.py"]
    entrypoints += list((ROOT / "scripts/fpga").glob("*.py"))
    entrypoints += list((ROOT / "scripts/fpga/validation").glob("*.py"))
    for path in entrypoints:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            counts["python_entrypoints"] += 1
        except (OSError, SyntaxError) as exc:
            failures.append(f"Python entrypoint: {exc}")

    v4 = ROOT / "model/chassis/v4-lidar-imu"
    for name in ["EdgeMind_Chassis.FCStd", "EdgeMind_Assembly.step", "preview-meshes.json",
                 "parameters.json", "verification.json"]:
        require((v4 / name).is_file(), f"Required V4 input missing: {name}")
        counts["retained_assets"] += 1
    v5 = ROOT / "model/chassis/v5-rgb-touch-display"
    for name in ["EdgeMind_Chassis.FCStd", "EdgeMind_Assembly.step", "ThirdDeck.stl",
                 "ThirdDeck-drawing.svg", "查看模型.html", "vendor/three.LICENSE.txt"]:
        require((v5 / name).is_file(), f"Required V5 asset missing: {name}")
        counts["retained_assets"] += 1
    try:
        moves = load(ROOT / "output/project-maintenance-20261104/MOVES.json")
        for item in moves["moves"]:
            path = ROOT / item["destination"]
            # Active status and human documentation are intentionally editable.
            # MOVES retains their original relocation hashes as provenance.
            if path.name == "STATUS.json" or path.suffix.lower() == ".md":
                continue
            require(digest(path) == item["sha256"], f"Relocated content changed: {path}")
            counts["retained_assets"] += 1
    except (OSError, KeyError, ValueError) as exc:
        failures.append(f"Relocation evidence: {exc}")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=False)
    report = {"passed": not failures, "scope": "local_documentation_and_frozen_build_evidence",
              "counts": counts, "head": head.stdout.strip(), "failures": failures,
              "network_accessed": False, "hardware_accessed": False,
              "historical_output_docs_excluded": True,
              "cache_deletion_complete": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
