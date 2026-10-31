"""Recompute the installed rear-sector model from the current geometry and RTL."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1] / 'code/camera-car-control/a745-autonomous'


def main():
    geometry_path = PROJECT / 'config/geometry.json'
    calibration_path = PROJECT / 'config/calibration.json'
    autonomy_path = PROJECT / 'rtl/a745_autonomy.v'
    core_path = PROJECT / 'rtl/a745_core.v'
    scan_path = PROJECT / 'rtl/a745_navigation_scan.v'
    inputs = [geometry_path, calibration_path, autonomy_path, core_path,
              scan_path, Path(__file__).resolve()]
    geometry = json.loads(geometry_path.read_text())
    calibration = json.loads(calibration_path.read_text())
    autonomy, core, scan = [p.read_text() for p in (autonomy_path, core_path, scan_path)]
    revision = int(re.search(r"snapshot\[159:128\]<=32'd(\d+)", core)[1])
    stop = int(re.search(r'\bREAR_STOP_MM=(\d+)', autonomy)[1])
    nominal = int(re.search(r"REVERSE_LEFT_COUNTS=\(64'd(\d+)\*1000000000\*LEFT_CPR\)", core)[1])
    assert f"REVERSE_RIGHT_COUNTS=(64'd{nominal}*1000000000*RIGHT_CPR)" in core
    assert core.count("/(64'd3141593*") == 2
    counts = [nominal * 1000000000 * cpr // (3141593 * diameter)
              for cpr, diameter in zip(calibration['wheel_cpr'], calibration['wheel_diameter_um'])]
    assert counts == [705, 706]
    assert '.REVERSE_LEFT_COUNTS(REVERSE_LEFT_COUNTS)' in core
    assert '.REVERSE_RIGHT_COUNTS(REVERSE_RIGHT_COUNTS)' in core
    assert 'rear>REAR_STOP_MM && rear!=65535' in autonomy
    assert 'reverse_delta_l<=-$signed(32\'(REVERSE_LEFT_COUNTS))' in autonomy
    assert 'reverse_delta_r<=-$signed(32\'(REVERSE_RIGHT_COUNTS))' in autonomy
    low, high = map(int, re.search(r'in_rear=body2>=(\d+) && body2<=(\d+)', scan).groups())
    assert (low, high) == (13500, 22500)
    footprint = geometry['vehicle_outer_footprint_mm']
    lx, ly = geometry['lidar_origin_in_axle_frame_mm'][:2]
    margin = 40
    rear_x = min(p[0] for p in footprint) - margin
    min_y = min(p[1] for p in footprint) - margin
    max_y = max(p[1] for p in footprint) + margin
    radius = max(math.hypot(rear_x - lx, y - ly) for y in (min_y, max_y))
    assert stop > radius
    # Verify every point along the newly exposed rear edge remains in the
    # measured rear sector, including during the nominal reverse translation.
    checked = 0
    for travel in range(nominal + 1):
        for i in range(101):
            y = min_y + (max_y - min_y) * i / 100
            angle = math.degrees(math.atan2(y - ly, rear_x - travel - lx)) % 360 * 100
            assert low <= angle <= high, (travel, y, angle)
            checked += 1
    result = dict(passed=True, firmware_revision=revision,
                  generated_by=str(Path(__file__).resolve()),
                  recorded_utc=datetime.now(timezone.utc).isoformat(),
                  rear_stop_mm=stop, inflated_rear_extent_from_lidar_mm=lx - rear_x,
                  inflated_half_width_mm=max(abs(min_y - ly), abs(max_y - ly)),
                  inflated_rear_corner_radius_mm=radius,
                  rear_sector_covers_new_rear_edge=True,
                  checked_rear_sector_points=checked,
                  reverse_wheel_count_limits=counts, reverse_nominal_mm=nominal,
                  model_only=True, physical_measurement=False,
                  inputs_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    target = OUT / f'reverse-clearance-{revision}.json'
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
