"""Package a committed checkpoint as a verifiable delta; never include LFS blobs or local secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    base = git("rev-parse", args.base + "^{commit}").decode().strip()
    commit = git("rev-parse", args.commit + "^{commit}").decode().strip()
    subprocess.run(["git", "merge-base", "--is-ancestor", base, commit], cwd=ROOT, check=True)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    names = git("diff", "--name-only", "-z", "--no-renames", "--diff-filter=ACMT", base, commit)
    deleted = git("diff", "--name-only", "-z", "--no-renames", "--diff-filter=D", base, commit)
    entries = {}
    for name in names.decode("utf-8").split("\0"):
        if not name:
            continue
        content = git("show", commit + ":" + name)
        if content.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            raise RuntimeError("Changed LFS object needs separate packaging: " + name)
        entries["files/" + name] = content
    entries["progress.patch"] = git("diff", "--binary", "--full-index", "--no-ext-diff", "--no-renames", base, commit)
    entries["PACKAGE-README.md"] = f"""# EdgeMind-Robot source progress checkpoint

This is a DELTA package, not a complete offline repository or working FPGA firmware.
Base commit: `{base}`
Checkpoint commit: `{commit}`
Repository: https://github.com/Tinsiag/EdgeMind-Robot
Branch: codex/avoidance-handoff-20261025

57 RTL benches and 61 Python tests passed on the saved Linux VM inputs.
PNR FAILED with 7463 unrouted nets. No new .fs, final timing sign-off or hardware acceptance.
Read files/HANDOFF-20261025.md and files/NEXT-AI-PROMPT-20261025.md (Chinese).

Preferred restoration: clone the checkpoint branch and run git lfs pull/fsck.
To apply this delta instead, use a NEW clean clone/worktree at the exact base:

```bash
git clone https://github.com/Tinsiag/EdgeMind-Robot.git EdgeMind-restore
cd EdgeMind-restore
git checkout --detach {base}
git status --porcelain  # must be empty
git apply --check /absolute/path/to/unpacked/progress.patch
git apply --index /absolute/path/to/unpacked/progress.patch
git write-tree
git lfs pull
git lfs fsck
```

Expected Git tree after applying: `{git('rev-parse', commit + '^{tree}').decode().strip()}`.
The patch adds/updates/deletes all changes since base. files/ is a review copy;
do not blindly copy it over an existing checkout or overwrite uncommitted work.
MANIFEST.json records SHA-256 and size for each ZIP entry except itself.
Verify the downloaded ZIP against its sibling .sha256 before extracting.
CAD/history LFS objects, IDE/Programmer, licenses, Python venv, generated platform,
implementation databases and any previous known-good bitstream are not included.
Recreate the Linux environment and generated inputs using the handoff instructions.
""".encode("utf-8")
    manifest = {
        "schema": 1, "kind": "source-progress-delta", "base_commit": base,
        "checkpoint_commit": commit,
        "checkpoint_tree": git("rev-parse", commit + "^{tree}").decode().strip(),
        "deleted_paths": [p for p in deleted.decode("utf-8").split("\0") if p],
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(entries.items())],
    }
    entries["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for row in manifest["files"]:
            data = archive.read(row["path"])
            assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "  " + output.name + "\n", encoding="ascii")
    print(json.dumps({"zip": str(output), "sha256": digest, "entries": len(entries),
                      "bytes": output.stat().st_size, "commit": commit}, indent=2))


if __name__ == "__main__":
    main()
