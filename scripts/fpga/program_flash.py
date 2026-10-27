"""Program a complete ACG720 GW5AT-60B boot image into external SPI Flash.

Without --program this only validates the file and prints the command plan.
Cold boot and application checks remain separate physical verification steps.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
DEVICE = "GW5AT-60B"
VERIFY_SUCCESS = re.compile(
    r"\bverif(?:y|ication)\b[^\r\n]{0,120}\bsuccess(?:ful(?:ly)?)?\b", re.I
)
FAILURE = re.compile(r"\b(?:error|failed|failure|unable|cannot)\b", re.I)
STATUS_CODE = re.compile(r"Status Code\s*(?:is)?\s*:\s*(0x[0-9a-f]+)", re.I)
USER_CODE = re.compile(r"User Code\s*(?:is)?\s*:\s*(0x[0-9a-f]+)", re.I)
# UG718-1.0.4, table5-1: do not confuse successful Reprogram command
# completion with completed configuration. Older logs captured0x30000460
# with wakeup/done still low immediately after Reprogram.
READY_MASK = (1 << 30) | (1 << 29) | (1 << 28) | (1 << 13)
CONFIG_ERROR_MASK = (1 << 27) | (1 << 21) | (1 << 19) | (1 << 9) | (1 << 4) | 0xF
CONFIG_TIMEOUT_SECONDS = 60


def bitstream_user_code(path):
    with path.open("rb") as stream:
        header = stream.read(8192).decode("ascii", errors="replace")
    match = re.search(r"(?mi)^//UserCode:\s*(0x[0-9a-f]{1,8})\s*$", header)
    if not match:
        raise ValueError("Bitstream has no readable UserCode header; hardware not touched")
    return int(match[1], 16)


def configuration_status(evidence):
    matches = STATUS_CODE.findall(evidence)
    if not matches or len({int(value, 16) for value in matches}) != 1:
        raise RuntimeError("Missing or inconsistent FPGA status register evidence")
    value = int(matches[0], 16)
    return {"raw": f"0x{value:08X}", "wakeup": bool(value & (1 << 30)),
            "done": bool(value & (1 << 13)), "error_bits": f"0x{value & CONFIG_ERROR_MASK:08X}",
            "ready": (value & READY_MASK) == READY_MASK and not value & ((1 << 31) | CONFIG_ERROR_MASK)}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parser():
    gowin = Path(os.environ.get("GOWIN_HOME", r"C:\Gowin\Gowin_V1.9.12.04_x64"))
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bitstream", type=Path, required=True)
    p.add_argument("--sha256", required=True, help="Expected SHA-256 of the selected image")
    p.add_argument("--programmer", type=Path, default=gowin / "Programmer/bin/programmer_cli.exe")
    p.add_argument("--cable-index", type=int, choices=(0, 1, 3, 4, 5), default=1,
                   help="Gowin cable type: 0 GWU2X, 1 FT2CH, 3 Digilent, 4 Debugger A, 5 WINUSB")
    p.add_argument("--channel", type=int, choices=(0, 1), default=0)
    p.add_argument("--location", type=int, help="Optional USB cable location, overrides channel")
    p.add_argument("--log-dir", type=Path,
                   default=ROOT / "code/camera-car-control/.local/programming")
    p.add_argument("--program", action="store_true", help="Execute the Flash write and reload")
    return p


def validate(args):
    image = args.bitstream.resolve(strict=True)
    if image.suffix.lower() != ".fs" or not image.is_file() or image.stat().st_size == 0:
        raise ValueError("A non-empty complete .fs bitstream is required")
    expected = args.sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("--sha256 must be exactly 64 hexadecimal characters")
    if sha256(image) != expected:
        raise ValueError("Bitstream SHA-256 mismatch; no hardware operation performed")
    if not args.programmer.is_file():
        raise FileNotFoundError(f"Programmer not found: {args.programmer}")
    bitstream_user_code(image)
    return image, expected


def commands(args, image):
    common = [str(args.programmer.resolve()), "--device", DEVICE,
              "--cable-index", str(args.cable_index),
              "--chain_index", "0", "--chain_size", "1", "--frequency", "2.5MHz"]
    if args.location is not None:
        common += ["--location", str(args.location)]
    else:
        common += ["--channel", str(args.channel)]
    return [
        ("flash_program_verify", common + ["--run", "54", "--spiaddr", "0x000000", "--fsFile", str(image)]),
        ("reprogram", common + ["--run", "1"]),
        ("read_status", common + ["--run", "74"]),
        ("read_user_code", common + ["--run", "73"]),
    ]


def save_audit(folder, audit):
    temporary = folder / "audit.tmp"
    temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "audit.json")


def decode_output(output):
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError:
        return output.decode("mbcs" if os.name == "nt" else "latin-1", errors="replace")


def run_step(args, folder, audit, name, command, announce=True):
    vendor_log = folder / f"{name}.vendor.log"
    command = command + ["--output", str(vendor_log)]
    step = {"name": name, "command": command, "state": "running"}
    audit["steps"].append(step)
    audit["state"] = name
    save_audit(folder, audit)
    if announce:
        print(f"Running {name}; do not disconnect board power.", flush=True)
    try:
        result = subprocess.run(command, cwd=args.programmer.resolve().parent,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=15 if name.startswith("read_") else 900, check=False)
    except subprocess.TimeoutExpired as exc:
        (folder / f"{name}.console.log").write_text(decode_output(exc.output), encoding="utf-8")
        raise RuntimeError(f"{name} timed out; operation incomplete, no automatic rewrite") from exc
    output = decode_output(result.stdout)
    (folder / f"{name}.console.log").write_text(output, encoding="utf-8")
    step["returncode"] = result.returncode
    evidence = output + (decode_output(vendor_log.read_bytes()) if vendor_log.is_file() else "")
    if result.returncode != 0 or FAILURE.search(evidence):
        raise RuntimeError(f"{name} failed; see logs. No retry or SRAM fallback was attempted")
    if name == "flash_program_verify" and not VERIFY_SUCCESS.search(evidence):
        raise RuntimeError("Programmer did not report successful Flash verification; reload was not attempted")
    step["state"] = "completed"
    save_audit(folder, audit)
    return evidence


def execute(args, image, expected):
    # Stage the exact checked image so later build activity cannot change it.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    folder = args.log_dir.resolve() / stamp
    folder.mkdir(parents=True, exist_ok=False)
    audit = {"schema": 2, "started_utc": stamp, "device": DEVICE,
             "original_bitstream": str(image), "sha256": expected,
             "flash_address": "0x000000", "flash_program_verify_completed": False,
             "reload_command_completed": False, "status_read_completed": False,
             "configuration_ready": False, "user_code_verified": False,
             "expected_user_code": f"0x{bitstream_user_code(image):08X}",
             "cold_boot_verified": False, "application_verified": False,
             "state": "preparing", "steps": []}
    save_audit(folder, audit)
    try:
        staged = folder / "image.fs"
        shutil.copyfile(image, staged)
        if sha256(staged) != expected:
            raise ValueError("Image changed while staging; Flash has not been written")
        audit["staged_bitstream"] = str(staged)
        audit["programmer_sha256"] = sha256(args.programmer)
        for name, command in commands(args, staged):
            evidence = run_step(args, folder, audit, name, command)
            if name == "flash_program_verify":
                audit["flash_program_verify_completed"] = True
            elif name == "reprogram":
                audit["reload_command_completed"] = True
            elif name == "read_status":
                deadline = time.monotonic() + CONFIG_TIMEOUT_SECONDS
                poll = 0
                while True:
                    status = configuration_status(evidence)
                    audit.setdefault("configuration_status_samples", []).append(status)
                    audit["status_read_completed"] = True
                    save_audit(folder, audit)
                    if int(status["error_bits"], 16):
                        raise RuntimeError(f"FPGA configuration error: {status['raw']}; no rewrite attempted")
                    if status["ready"]:
                        audit["configuration_ready"] = True
                        audit["final_status_register"] = status["raw"]
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("FPGA wakeup/DONE did not assert before timeout; no rewrite attempted")
                    if poll == 0:
                        print("Waiting for FPGA wakeup/DONE; polling is read-only.", flush=True)
                    time.sleep(0.5)
                    poll += 1
                    evidence = run_step(args, folder, audit, f"read_status_{poll:03d}", command, announce=False)
                audit["status_read_completed"] = True
            elif name == "read_user_code":
                values = USER_CODE.findall(evidence)
                if not values or len({int(value, 16) for value in values}) != 1:
                    raise RuntimeError("Missing or inconsistent User Code evidence")
                audit["read_user_code"] = f"0x{int(values[0], 16):08X}"
                if int(values[0], 16) != bitstream_user_code(staged):
                    raise RuntimeError("Loaded User Code does not match staged image; no rewrite attempted")
                audit["user_code_verified"] = True
            save_audit(folder, audit)
        audit["state"] = "flash_verified_awaiting_cold_boot_and_application_check"
        save_audit(folder, audit)
        print(f"Flash verified, FPGA wakeup/DONE ready and User Code matched. Cold boot and application checks are still pending.\nAudit: {folder / 'audit.json'}")
        return 0
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        audit["state"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        if audit["steps"] and audit["steps"][-1]["state"] == "running":
            audit["steps"][-1]["state"] = audit["state"]
        audit["error"] = str(exc) or "Interrupted by operator"
        save_audit(folder, audit)
        print(f"Incomplete: {audit['error']}\nAudit: {folder / 'audit.json'}", file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        image, expected = validate(args)
        if not args.program:
            print(f"PREVIEW ONLY; no Programmer process or hardware operation.\nImage: {image}\nSHA-256: {expected}")
            for name, command in commands(args, image):
                print(name + ": " + subprocess.list2cmdline(command))
            print("After Reprogram: poll status read-only until wakeup/DONE, then match User Code to the staged image.")
            print("Execution requires --program. Power off motor VM before writing/reloading.")
            return 0
        return execute(args, image, expected)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
