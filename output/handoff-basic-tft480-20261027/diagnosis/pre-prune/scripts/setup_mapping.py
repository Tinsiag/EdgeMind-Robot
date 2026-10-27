"""Fetch pinned upstream CoreSLAM sources and build a replaceable local DLL."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "simondlevy/BreezySLAM"


def api(path):
    request = urllib.request.Request("https://api.github.com/repos/"+REPOSITORY+"/"+path,
                                     headers={"User-Agent": "EdgeMind-local-build"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def main():
    source = ROOT / "third_party/coreslam"
    source.mkdir(parents=True, exist_ok=True)
    manifest_file = source / "provenance.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else None
    commit = manifest["commit"] if manifest else "1170285cd42a88300eddd275fc3df36e642e3a2e"
    paths = ["LICENSE.md", "c/coreslam.c", "c/coreslam.h", "c/coreslam_internals.h",
             "c/coreslam_sisd.c", "c/random.c", "c/random.h", "c/ziggurat.c", "c/ziggurat.h"]
    hashes = {}
    for path in paths:
        target = source / Path(path).name
        if not target.exists():
            record = api("contents/"+path+"?ref="+commit)
            target.write_bytes(base64.b64decode(record["content"]))
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if manifest and manifest["sha256"].get(path) != digest:
            raise RuntimeError("Upstream source changed locally: "+path)
        hashes[path] = digest
    # LGPL v3 incorporates GPL v3; ship both license texts.
    license_file = source / "GPL-3.0.txt"
    if not license_file.exists():
        request = urllib.request.Request("https://api.github.com/repos/spdx/license-list-data/contents/text/GPL-3.0-or-later.txt",
                                         headers={"User-Agent": "EdgeMind-local-build"})
        with urllib.request.urlopen(request, timeout=45) as response:
            license_file.write_bytes(base64.b64decode(json.load(response)["content"]))
    manifest_file.write_text(json.dumps({"repository": REPOSITORY, "commit": commit,
        "license": "LGPL-3.0-or-later", "sha256": hashes}, indent=2)+"\n", encoding="utf-8", newline="\n")
    destination = ROOT / ".local/mapping"
    destination.mkdir(parents=True, exist_ok=True)
    import ziglang
    zig = Path(ziglang.__file__).parent / "zig.exe"
    subprocess.run([str(zig), "cc", "-shared", "-O2", "-std=c99", "-DM_PI=3.14159265358979323846", "-I", str(source),
        str(ROOT / "native/slam_bridge.c"), *[str(source / name) for name in
        ("coreslam.c", "coreslam_sisd.c", "random.c", "ziggurat.c")],
        "-o", str(destination / "edgemind_slam.dll")], check=True)
    print(destination / "edgemind_slam.dll")


if __name__ == "__main__":
    main()
