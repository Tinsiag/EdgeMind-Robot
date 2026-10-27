"""Package/verify a paused project. No EDA, programming, or hardware actions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
NAME = "EdgeMind-Robot-handoff-20261028"
OUT = ROOT / "output"
READING = OUT / "handoff-20261028"
META = "HANDOFF-METADATA"


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def git(*args):
    exe = shutil.which("git")
    if not exe:
        exe = str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")
    return subprocess.check_output([exe, *args], cwd=ROOT)


def excluded(path):
    if "__pycache__" in path.split("/") or path.endswith(".pyc"):
        return "Python bytecode cache"
    if path.startswith("output/handoff/"):
        return "Repeated older handoff ZIPs and expanded copies; preserved in Git history/worktree"
    if path.startswith("output/" + NAME):
        return "This package and its outside verification files; avoid recursion"
    if path in {"output/handoff-20261028.zip", "output/handoff-20261028.zip.sha256"}:
        return "Reading ZIP duplicates included reading directory"
    if path.startswith("output/EdgeMind-Robot-basic-tft480-handoff-20261027.zip"):
        return "Previous ZIP duplicates included handoff-basic-tft480-20261027 directory"
    return None


def refresh_reading():
    # Update existing copied files from their originals; do not delete archives.
    for folder in ["root", "evidence"]:
        for target in (READING / folder).rglob("*"):
            if target.is_file():
                rel = target.relative_to(READING / folder)
                source = ROOT / rel
                if source.is_file():
                    shutil.copy2(source, target)
    extras = ["HANDOFF-20261027.md", "NEXT-AI-PROMPT-20261027.md", "RESUME-20261027.md"]
    for name in extras:
        shutil.copy2(ROOT / name, READING / "root" / name)
    for name in ["clock-routing-outcome.json", "attempt3-local-clock-pr0004/result.json",
                 "attempt3-local-clock-pr0004/build.log", "attempt3-local-clock-pr0004/impl/pnr/cmd.do",
                 "attempt3-local-clock-pr0004/impl/pnr/a741.rpt.txt"]:
        relative = Path("output/motion-tft800-20261028") / name
        dst = READING / "evidence" / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, dst)
    (READING / "SOURCE-AND-GIT-STATE.txt").write_bytes(
        b"Pre-handoff base HEAD: " + git("rev-parse", "HEAD") + b"\n" + git("status", "--short"))
    (READING / "DIFF-STAT.txt").write_bytes(git("diff", "--stat", "HEAD"))
    rows = []
    for p in sorted(READING.rglob("*")):
        if p.is_file() and p.name != "CONTENTS-SHA256.json":
            rows.append({"path": p.relative_to(READING).as_posix(), "bytes": p.stat().st_size,
                         "sha256": sha_file(p)})
    (READING / "CONTENTS-SHA256.json").write_bytes(encoded({"files": rows}))
    zpath = OUT / "handoff-20261028.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(READING.rglob("*")):
            if p.is_file():
                z.write(p, "handoff-20261028/" + p.relative_to(READING).as_posix())
    zpath.with_suffix(".zip.sha256").write_text(sha_file(zpath) + "  " + zpath.name + "\n", encoding="ascii")


def pack():
    refresh_reading()
    names = set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8").split("\0")) - {""}
    names.update(p.relative_to(ROOT).as_posix() for p in OUT.rglob("*") if p.is_file())
    inputs, omissions = [], []
    for name in sorted(names):
        path = ROOT / name
        if not path.is_file():
            continue  # Tracked deletions stay deleted in the snapshot.
        reason = excluded(name)
        if reason:
            omissions.append({"path": name, "bytes": path.stat().st_size, "reason": reason})
        else:
            inputs.append(name)
    # All input enumeration is frozen before opening the new ZIP.
    path = OUT / (NAME + ".zip")
    pending = OUT / (NAME + ".zip.partial")
    rows = []
    total = sum((ROOT / name).stat().st_size for name in inputs)
    print(f"Packaging {len(inputs)} files, {total:,} input bytes", flush=True)
    progress = time.monotonic()
    with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for i, name in enumerate(inputs):
            src = ROOT / name
            h = hashlib.sha256()
            count = 0
            # Hash exactly the bytes streamed to the ZIP, without EDA or rewrite.
            zi = zipfile.ZipInfo.from_file(src, arcname=name)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi._compresslevel = 6
            with src.open("rb") as origin, z.open(zi, "w", force_zip64=True) as target:
                for block in iter(lambda: origin.read(1024 * 1024), b""):
                    h.update(block)
                    count += len(block)
                    target.write(block)
            rows.append({"path": name, "bytes": count, "sha256": h.hexdigest()})
            if time.monotonic() - progress > 20:
                print(f"Packed {i + 1}/{len(inputs)} files", flush=True)
                progress = time.monotonic()
        manifest = {"format": 1, "snapshot": "2026-10-28 paused handoff",
                    "base_git_commit": git("rev-parse", "HEAD").decode().strip(),
                    "file_count": len(rows), "uncompressed_bytes": total, "files": rows}
        z.writestr(META + "/PACKAGE-MANIFEST.json", encoded(manifest))
        z.writestr(META + "/EXCLUSIONS.json", encoded({"files": omissions, "not_enumerated": [
            ".git internal object database and credentials",
            "Ignored .venv, local runtimes/tool installations/downloads",
            "Unrelated .local caches; exact build inputs and used example ZIPs are archived separately",
            "External manufacturer library, except project-used example input archives"]}))
        z.writestr(META + "/GIT-BASE-STATE.txt", git("status", "--short"))
    result = verify(pending)
    pending.replace(path)
    result["package"] = path.name
    path.with_suffix(".zip.sha256").write_text(result["zip_sha256"] + "  " + path.name + "\n", encoding="ascii")
    (OUT / (NAME + "-VERIFY.json")).write_bytes(encoded(result))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


def verify(path):
    print("Verifying ZIP CRC and every archived file SHA-256", flush=True)
    verified = 0
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read(META + "/PACKAGE-MANIFEST.json"))
        assert len(z.namelist()) == len(set(z.namelist())), "Duplicate ZIP entry"
        golden = "output/tft800-official-20261028/build-evidence-final/a741.fs"
        golden_expected = "d5e558ad68ac665f889fcec651262714e52e40774853e5368c51f0fc2a1ad62b"
        rows = {entry["path"]: entry for entry in manifest["files"]}
        assert manifest["file_count"] == len(manifest["files"]) == len(rows), "Manifest count mismatch"
        metadata = {META + "/" + name for name in (
            "PACKAGE-MANIFEST.json", "EXCLUSIONS.json", "GIT-BASE-STATE.txt")}
        assert set(z.namelist()) == set(rows) | metadata, "Unlisted or missing ZIP entry"
        assert sum(entry["bytes"] for entry in rows.values()) == manifest["uncompressed_bytes"]
        assert rows[golden]["sha256"] == golden_expected
        for name, entry in rows.items():
            assert not name.startswith(("/", "\\")) and ".." not in Path(name).parts
            h = hashlib.sha256()
            size = 0
            with z.open(name) as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(data)
                    size += len(data)
            assert h.hexdigest() == entry["sha256"] and size == entry["bytes"], name
            verified += 1
        snapshots_verified = {}
        for name in rows:
            if name.endswith("/SOURCE-MAP.json") and ("/source-snapshot-d5/" in name or "/source-snapshot/" in name):
                mapping = json.loads(z.read(name))
                for source in mapping["entries"]:
                    archived = name.rsplit("/", 1)[0] + "/" + source["file"]
                    assert rows[archived]["sha256"] == source["sha256"], archived
                snapshots_verified[name] = len(mapping["entries"])
        assert len(snapshots_verified) == 4 and all(n == 111 for n in snapshots_verified.values()), snapshots_verified
        for name in z.namelist():
            if name.startswith(META + "/"):
                z.read(name)  # Also validate metadata CRCs.
    return {"package": path.name, "zip_sha256": sha_file(path), "zip_bytes": path.stat().st_size,
            "file_count": verified, "uncompressed_bytes": manifest["uncompressed_bytes"],
            "zip_crc_and_all_file_hashes_verified": True, "golden_d5_bitstream_verified": True,
            "original_sources_verified_by_source_maps": True,
            "source_snapshots": snapshots_verified,
            "base_git_commit": manifest["base_git_commit"],
            "eda_or_hardware_executed_for_handoff": False,
            "publication_status": "See Git commit and remote verification; this report describes package bytes only."}


def restore_inputs(manifest_path, destination):
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError("Destination must be an empty/new directory, never the active worktree")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in data["entries"]:
        rel = Path(row["workspace_path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe source-map path")
        source = manifest_path.parent / row["file"]
        assert sha_file(source) == row["sha256"], source
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(f"Restored {len(data['entries'])} verified inputs to {destination}; no build or hardware action.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("pack")
    check = sub.add_parser("verify")
    check.add_argument("zip", type=Path)
    restore = sub.add_parser("restore-inputs")
    restore.add_argument("source_map", type=Path)
    restore.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.action == "pack":
        pack()
    elif args.action == "verify":
        print(json.dumps(verify(args.zip), ensure_ascii=False, indent=2))
    else:
        restore_inputs(args.source_map, args.destination)
