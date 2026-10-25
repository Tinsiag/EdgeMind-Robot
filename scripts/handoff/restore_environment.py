"""Restore bundled ACG720 examples after a Git clone; never access hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "resources/vendor/acg720-examples"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate bundled files without restoring")
    args = parser.parse_args()
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    destination = ROOT / "code/camera-car-control/.local/environment/examples/GW5AT60K"
    checked = []
    for row in manifest["archives"]:
        source = (BUNDLE / "GW5AT60K" / row["path"]).resolve()
        target = (destination / row["path"]).resolve()
        if not source.is_relative_to((BUNDLE / "GW5AT60K").resolve()) or not target.is_relative_to(destination.resolve()):
            raise RuntimeError("Archive path escapes its intended directory")
        if not source.is_file() or source.stat().st_size != row["bytes"] or sha(source) != row["sha256"]:
            raise RuntimeError("Bundled archive missing or changed: " + row["path"])
        if target.exists() and sha(target) != row["sha256"]:
            raise RuntimeError("Keep existing local archive; content differs: " + str(target))
        checked.append((source, target))
    if not args.check:
        for source, target in checked:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
    print(json.dumps({"archives_verified": len(checked), "restored": not args.check,
        "examples": str(destination), "hardware_accessed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
