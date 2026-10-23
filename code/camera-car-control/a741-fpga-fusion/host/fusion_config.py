"""Shared build/host identity for immutable FPGA navigation geometry."""
import json
import math
import zlib


def compiled_parameters(geometry, calibration):
    verified=geometry.get("navigation_geometry_verified") is True
    radius=0;offset=[0,0,0]
    track=calibration["mechanical_track_um"]/1000
    if not 50<=track<=1000 or track!=geometry.get("wheel_track_mm"):
        raise ValueError("Geometry wheel track must match measured calibration")
    if verified:
        footprint=geometry.get("vehicle_outer_footprint_mm")
        offset=geometry.get("lidar_origin_in_axle_frame_mm")
        axle=geometry.get("wheel_axle_center_in_model_mm")
        height=geometry.get("lidar_height_mm")
        if not footprint or len(footprint)<3 or not offset or len(offset)!=3 or not axle or len(axle)!=3 or not height:
            raise ValueError("Verified geometry requires footprint, axle datum, lidar origin and height")
        if not all(len(p)==2 and all(math.isfinite(v) for v in p) for p in footprint):
            raise ValueError("Footprint must be finite axle-relative XY vertices")
        radius=math.ceil(max(math.hypot(*p) for p in footprint))
        if not 50<=radius<=750 or any(not math.isfinite(v) or abs(v)>2000 for v in offset) or not 0<height<=2000:
            raise ValueError("Geometry outside supported bounds")
    zero=calibration.get("lidar_zero_offset_deg",270)
    if not math.isfinite(zero):
        raise ValueError("Invalid lidar heading offset")
    values={"GEOMETRY_VERIFIED":int(verified),"RADIUS_MM":radius,"LIDAR_X":int(offset[0]),"LIDAR_Y":int(offset[1]),
            "TRACK_MM":round(track),"LIDAR_ZERO":round(zero*100)%36000,
            "LIDAR_CLOCKWISE":int(bool(calibration.get("lidar_clockwise",True)))}
    body=json.dumps({"schema":1,"parameters":values,"geometry":geometry},sort_keys=True,separators=(",",":"))
    return values,zlib.crc32(body.encode("utf-8"))
