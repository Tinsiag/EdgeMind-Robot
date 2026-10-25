"""Record regressions for shared video/transport and the reused RTL libraries."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

from check import ROOT, CAMERA


def main():
    out = ROOT / ".local/tests"
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in ("test_video.py", "test_control.py"):
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(CAMERA / "tests"),
                                 "-p", name, "-v"], capture_output=True, text=True, timeout=30)
        log = result.stdout+result.stderr
        (out / (name+".log")).write_text(log, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(log)
        results[name] = int(re.search(r"Ran (\d+) tests", log)[1])
    vision_file = CAMERA.parent / "fpga/acg720-vision-motion/.local/tests/results.json"
    vision = json.loads(vision_file.read_text(encoding="utf-8"))
    for name, expected in vision["input_sha256"].items():
        path = CAMERA.parent / "fpga" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Shared RTL changed since vision regression: "+name)
    (out / "related-vision-results.json").write_text(json.dumps(vision, indent=2), encoding="utf-8")
    results.update(vision_rtl_cases=len(vision["rtl_cases"]), vision_timestamp=vision["timestamp"],
                   hardware_tested=False, unix_time=time.time())
    (out / "related-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
