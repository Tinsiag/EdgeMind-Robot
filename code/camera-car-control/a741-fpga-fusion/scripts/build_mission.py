"""Build reproducible RV32I code and an 8 KiB BSRAM initialization image."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]


def cached_image():
    """Reuse only a complete pinned ROM whose source and decoded bytes match."""
    target = ROOT / "firmware/mission.hex"
    manifest = ROOT / "firmware/manifest.json"
    if not target.is_file() or not manifest.is_file():
        return None
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        names = {"link.ld", "mission.c", "start.S"}
        if set(record["inputs"]) != names or record["architecture"] != "rv32i/ilp32" or record["ram_bytes"] != 8192:
            return None
        if any(hashlib.sha256((ROOT/"firmware"/n).read_bytes()).hexdigest()!=h for n,h in record["inputs"].items()):
            return None
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest()!=record["hex_sha256"]:
            return None
        words = data.decode("ascii").split()
        if len(words)!=2048 or any(len(word)!=8 for word in words):
            return None
        raw = b"".join(int(word,16).to_bytes(4,"little") for word in words)
        size = record["program_bytes"]
        if not 0<size<=7168 or any(raw[size:]) or hashlib.sha256(raw[:size]).hexdigest()!=record["binary_sha256"]:
            return None
        return target,record
    except (KeyError, ValueError, OSError, TypeError, UnicodeError):
        return None


def build(force=False):
    cached = None if force else cached_image()
    if cached is not None:
        target,record = cached
        print(json.dumps({"reused_verified_rom":True,**record},indent=2))
        return target
    import ziglang
    zig = Path(ziglang.__file__).parent / ("zig.exe" if sys.platform == "win32" else "zig")
    out = ROOT / ".local/mission-firmware"
    out.mkdir(parents=True, exist_ok=True)
    elf = out / "mission.elf"
    command = [str(zig), "cc", "-target", "riscv32-freestanding", "-mcpu=generic_rv32", "-mabi=ilp32",
               "-Os", "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-stack-protector",
               "-mno-relax", "-msmall-data-limit=0", "-Wl,-T," + str(ROOT / "firmware/link.ld"),
               str(ROOT / "firmware/start.S"), str(ROOT / "firmware/mission.c"), "-o", str(elf)]
    subprocess.run(command, check=True, cwd=ROOT)
    binary = out / "mission.bin"
    subprocess.run([str(zig), "objcopy", "-O", "binary", str(elf), str(binary)], check=True)
    raw = binary.read_bytes()
    if len(raw) > 7168:
        raise RuntimeError("Mission firmware exceeds reserved program area")
    padded = raw.ljust(8192, b"\0")
    target = ROOT / "firmware/mission.hex"
    text = "".join(f"{int.from_bytes(padded[i:i+4], 'little'):08x}\n" for i in range(0, 8192, 4))
    image = text.encode("ascii")
    if not target.is_file() or target.read_bytes()!=image:
        target.write_bytes(image)
    record = {"architecture": "rv32i/ilp32", "ram_bytes": 8192, "program_bytes": len(raw),
              "binary_sha256": hashlib.sha256(raw).hexdigest(),
              "hex_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"firmware").iterdir() if p.suffix in (".c", ".S", ".ld")},
              "compiler": subprocess.check_output([str(zig), "version"], text=True).strip()}
    manifest = ROOT / "firmware/manifest.json"
    metadata = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    if not manifest.is_file() or manifest.read_bytes()!=metadata:
        manifest.write_bytes(metadata)
    print(json.dumps(record, indent=2))
    return target


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force",action="store_true",help="Recompile even when the pinned ROM and all sources match")
    build(parser.parse_args().force)
