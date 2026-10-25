"""Record user-provided MPU6050 reference hashes and check proposed ball conflicts."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
from check import ROOT, REPO, CAMERA


def main():
    reference = REPO / "doc/模块资料/mpu6050/测试程序"
    files = sorted(p for p in reference.rglob("*") if p.is_file())
    if not files:
        raise RuntimeError("MPU6050 reference source missing")
    pins = json.loads((ROOT / "config/sensor-pins.json").read_text(encoding="utf-8"))
    if pins.get("module_schematic_status") != "rejected_by_user_do_not_use_as_hardware_evidence":
        raise RuntimeError("The user-withdrawn schematic must not be restored as evidence")
    table = ROOT / pins["pin_assignment_file"]
    table_raw = table.read_bytes()
    # The supplied CSV has literal question marks in some Chinese labels.
    # Its signal, ball and I/O-standard columns remain readable ASCII.
    rows = list(csv.reader(io.StringIO(table_raw.decode("utf-8-sig"))))
    expected_signals = {"scl": ("L18", "COMS_SDAT"), "sda": ("M20", "COMS_SCLK"),
                        "xda": ("A1", "COMS_HREF"), "xcl": ("B2", "COMS_VS"),
                        "ad0": ("M17", "COMS_XCLK"), "int": ("B1", "COMS_PCLK")}
    documented = {}
    for purpose, (ball, original_signal) in expected_signals.items():
        if pins["mpu6050"][purpose]["ball"] != ball:
            raise RuntimeError("Pin mapping differs from the user's confirmed wiring: "+purpose)
        matches = [(index+1, row) for index, row in enumerate(rows) if len(row)>4 and row[2].strip()==ball]
        if len(matches)!=1 or matches[0][1][1].strip()!=original_signal or matches[0][1][4].strip()!="LVCMOS33":
            raise RuntimeError("Unexpected ball/signal/I/O standard in supplied CSV: "+ball)
        documented[purpose] = {"ball": ball, "csv_row": matches[0][0],
                               "original_signal": original_signal, "documented_io_standard": "LVCMOS33"}
    images = [ROOT / "docs/images/mpu6050-product-spec.jpg", ROOT / "docs/images/mpu6050-product-pins.jpg"]
    image_records = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in images}
    schematic = ROOT / pins["module_schematic_file"]
    withdrawn = {"path": schematic.relative_to(ROOT).as_posix(),
                 "status": "rejected_by_user", "usable_as_evidence": False}
    if schematic.is_file():
        withdrawn["sha256"] = hashlib.sha256(schematic.read_bytes()).hexdigest()
    balls = [v["ball"] for v in pins["mpu6050"].values() if isinstance(v, dict)]
    cst_path = ROOT / ".local/platform/a741.cst"
    cst = cst_path.read_text(encoding="utf-8")
    existing = {b: signal for signal, group in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);', cst)
                for b in group.split(",")}
    collisions = {b: existing[b] for b in balls if b in existing}
    if len(set(balls)) != len(balls) or collisions:
        raise RuntimeError("MPU6050 ball conflict: "+str(collisions))
    record = {"reference_files": {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              "withdrawn_module_schematic": withdrawn,
              "pin_assignment": {"path": table.relative_to(ROOT).as_posix(),
                                 "sha256": hashlib.sha256(table_raw).hexdigest(), "signals": documented},
              "product_images": image_records, "product_supply_range_v": [3, 5],
              "user_supply_v": 3.3, "proposed_balls": balls, "existing_cst_conflicts": collisions,
              "physical_pin_order_verified": False, "bank_voltage_verified": False,
              "actual_supply_measured": pins.get("actual_supply_measured", False),
              "user_voltage_measurement": pins.get("user_voltage_measurement"),
              "module_schematic_reviewed": False,
              "module_ad0_default_verified": False,
              "module_pullups_verified": False, "sensor_outputs_enabled": False}
    out = ROOT / "verification/mpu6050-reference.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("PASS reference/image hashes, six CSV LVCMOS33 assignments and ball conflict checks; old schematic withdrawn; electrical verification pending")


if __name__ == "__main__":
    main()
