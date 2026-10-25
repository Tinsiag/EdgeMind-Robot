"""Derive a conservative XY envelope from the complete V4/V5 CAD assembly.

Uses the saved exact B-rep verification, cross-checks both revisions and hashes
the source CAD. This is a CAD datum audit, not a physical vehicle measurement.
"""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]


def derive():
    base = REPO / "model/chassis"
    reports = [json.loads((base / v / "verification.json").read_text(encoding="utf-8"))
               for v in ("v4-lidar-imu", "v5-rgb-touch-display")]
    if any(not r.get("readback_verified") for r in reports):
        raise ValueError("CAD STEP readback verification missing")
    if any(abs(a-b) > .001 for a,b in zip(reports[0]["assembly_bounds_mm"], reports[1]["assembly_bounds_mm"])):
        raise ValueError("V4/V5 body envelopes differ; inspect model revision")
    report = reports[0]
    parts = {p["name"]:p["bounds"] for p in report["parts"]}
    left, right = parts["RearLWheel"], parts["RearRWheel"]
    axle_y = sum((p[1]+p[4])/2 for p in (left,right))/2
    axle_z = sum((p[2]+p[5])/2 for p in (left,right))/2
    model_track = ((right[0]+right[3])-(left[0]+left[3]))/2
    measured_track = json.loads((ROOT/"config/calibration.json").read_text(encoding="utf-8"))["mechanical_track_um"]/1000
    # Preserve the user's measured kinematic track. Enlarge the CAD bounds by
    # half the discrepancy on each side; never shrink an existing envelope.
    lateral_margin = max(0, measured_track-model_track)/2
    b = report["assembly_bounds_mm"]
    front, rear = math.ceil(axle_y-b[1]), math.ceil(b[4]-axle_y)
    half_width = math.ceil(max(abs(b[0]),abs(b[3]))+lateral_margin)
    lx, ly = report["lidar"]["center_xy"]
    geometry = json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8"))
    geometry.update({"vehicle_outer_footprint_mm":[[-rear,-half_width],[front,-half_width],[front,half_width],[-rear,half_width]],
        "wheel_axle_center_in_model_mm":[0,round(axle_y,6),round(axle_z,6)],
        "lidar_origin_in_axle_frame_mm":[round(axle_y-ly,6),round(lx,6),0],
        "lidar_height_mm":None,
        "lidar_optical_height_range_mm":[round(report["optical_zone_check"]["starts_z"],6),round(b[5],6)],
        "navigation_geometry_verified":True,"navigation_enabled":True,"physical_geometry_verified":False,
        "reason_locked":"", "geometry_authority":"User requested CAD-derived geometry, 2026-10-24; XY navigation only. Optical-window height interval is not an exact laser plane.",
        "cad_navigation_audit":{"model_version":"v4-lidar-imu, cross-checked against v5-rgb-touch-display",
            "assembly_bounds_mm":b,"model_wheel_center_track_mm":model_track,"measured_track_mm":measured_track,
            "added_lateral_margin_each_side_mm":lateral_margin,"forward_axis":"navigation X = -CAD Y, navigation Y = CAD X",
            "lidar_z_offset_used":False,"front_extent_mm":front,"rear_extent_mm":rear,"half_width_mm":half_width,
            "source_sha256":{str(p.relative_to(REPO)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                for v in ("v4-lidar-imu","v5-rgb-touch-display")
                for p in (base/v/"verification.json",base/v/"parameters.json",base/v/"EdgeMind_Assembly.step")}}})
    (ROOT/"config/geometry.json").write_text(json.dumps(geometry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(geometry["cad_navigation_audit"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    derive()
