"""Prepare or perform a bounded, read-only ACG720 JTAG capture.

Default mode inventories the PC and download cables only. --watch must be
started separately after hardware checks. A time budget cannot make powering
an overheating board safe; this script cannot switch off USB power.
"""

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


CLI = Path(r"C:\Gowin\Gowin_V1.9.12_x64\Programmer\bin\programmer_cli.exe")
EXPECTED_ID = "0x0001481b"
READ_OPERATIONS = ((0, "device-codes"), (74, "status"), (73, "user-code"))
LOCAL_TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(LOCAL_TZ).isoformat()


def run_command(args, timeout):
    started = time.monotonic()
    result = {"time": now(), "arguments": args}
    try:
        proc = subprocess.run(
            args, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        result.update(exit_code=proc.returncode,
                      stdout=proc.stdout.decode("utf-8", errors="replace"),
                      stderr=proc.stderr.decode("utf-8", errors="replace"),
                      timed_out=False)
    except subprocess.TimeoutExpired as exc:
        result.update(exit_code=None, timed_out=True,
                      stdout=(exc.stdout or b"").decode("utf-8", errors="replace"),
                      stderr=(exc.stderr or b"").decode("utf-8", errors="replace"))
    result["elapsed_seconds"] = round(time.monotonic() - started, 4)
    return result


def locations(output):
    return sorted(set(re.findall(
        r"Gowin USB Cable\(FT2CH\).*?USB location:\s*(\d+)", output
    )))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true",
                        help="Explicitly wait for a cable and read once; cannot cut power")
    parser.add_argument("--wait-seconds", type=float, default=60)
    parser.add_argument("--read-budget-seconds", type=float, default=2)
    opts = parser.parse_args()
    if not 0 < opts.wait_seconds <= 120 or not 0 < opts.read_budget_seconds <= 5:
        parser.error("wait must be (0,120] seconds; read budget must be (0,5] seconds")
    if not CLI.is_file():
        raise SystemExit(f"Missing programmer: {CLI}")

    folder = Path(__file__).resolve().parent / "logs" / datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S-%f")
    folder.mkdir(parents=True)
    log = {"started": now(), "mode": "watch" if opts.watch else "prepare",
           "expected_id": EXPECTED_ID, "events": [],
           "can_switch_off_power": False,
           "read_budget_is_not_safe_power_on_duration": True}

    def save():
        (folder / "capture.json").write_text(
            json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record(name, result):
        log["events"].append({"name": name, **result})
        save()

    if not opts.watch:
        inventory = "$d = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\\*' -or $_.Class -eq 'Ports' } | Select-Object Status,Class,FriendlyName,InstanceId); ConvertTo-Json -InputObject $d -Depth 4"
        record("usb-inventory", run_command(
            ["powershell.exe", "-NoProfile", "-Command", inventory], 15))
        scan = run_command([str(CLI), "--scan-cables"], 2)
        record("cable-inventory", scan)
        log["cable_locations"] = locations(scan["stdout"])
        log["result"] = "prepared_only_no_fpga_registers_read"
    else:
        print("Waiting for one FT2CH cable. Hardware checks must be completed first.", flush=True)
        print("This process cannot switch off USB power.", flush=True)
        wait_deadline = time.monotonic() + opts.wait_seconds
        selected = None
        previous_scan = None
        while time.monotonic() < wait_deadline:
            scan = run_command([str(CLI), "--scan-cables"],
                               min(1, max(0.01, wait_deadline - time.monotonic())))
            current = (scan["stdout"], scan["stderr"], scan["exit_code"], scan["timed_out"])
            if current != previous_scan:
                record("cable-scan", scan)
                previous_scan = current
            found = locations(scan["stdout"])
            if len(found) > 1:
                log["result"] = "multiple_cables_no_target_selected"
                break
            if found and not scan["timed_out"] and scan["exit_code"] == 0:
                selected = found[0]
                break
            if scan["timed_out"] or scan["exit_code"] != 0:
                log["result"] = "cable_scan_failed_no_retry"
                break
            time.sleep(min(0.1, max(0, wait_deadline - time.monotonic())))
        if selected:
            log["location"] = selected
            log["detected_at"] = now()
            read_deadline = time.monotonic() + opts.read_budget_seconds
            for operation, label in READ_OPERATIONS:
                remaining = read_deadline - time.monotonic()
                if remaining <= 0:
                    log["result"] = "read_budget_exhausted"
                    break
                # Only the three documented read operations above are accepted.
                result = run_command(
                    [str(CLI), "--device", "GW5AT-60B", "--operation_index", str(operation),
                     "--cable-index", "1", "--location", selected, "--frequency", "2.5MHz"],
                    remaining)
                record(label, result)
                print(result["stdout"], flush=True)
                if result["timed_out"] or result["exit_code"] != 0:
                    log["result"] = "read_failed_no_retry"
                    break
                if operation == 0 and EXPECTED_ID not in result["stdout"].lower():
                    log["result"] = "expected_device_id_not_confirmed"
                    break
            else:
                log["result"] = "read_sequence_completed_review_raw_outputs"
            print("Read attempt finished. Disconnect board power now.", flush=True)
        elif "result" not in log:
            log["result"] = "no_cable_before_deadline"
    log["finished"] = now()
    save()
    print(json.dumps({"result": log["result"], "log": str(folder / "capture.json"),
                      "cable_locations": log.get("cable_locations", [])}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
