"""Read-only STL/STEP provenance. Does not infer wheel or laser datums from vertices."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def inspect(stl, step):
    blob=stl.read_bytes()
    if len(blob)<84:
        raise ValueError("Binary STL header missing")
    count=struct.unpack_from("<I",blob,80)[0]
    if len(blob)!=84+50*count:
        raise ValueError("Expected complete binary STL")
    minimum=[float("inf")]*3;maximum=[float("-inf")]*3
    for triangle in struct.iter_unpack("<12fH",blob[84:]):
        for vertex in (triangle[3:6],triangle[6:9],triangle[9:12]):
            for axis,value in enumerate(vertex):
                minimum[axis]=min(minimum[axis],value);maximum[axis]=max(maximum[axis],value)
    data=step.read_bytes();text=data.decode("utf-8",errors="replace")
    return {"stl":{"path":str(stl.resolve()),"sha256":hashlib.sha256(blob).hexdigest(),"triangles":count,
                    "bounds":[minimum,maximum],"extents":[maximum[i]-minimum[i] for i in range(3)],
                    "unit":"STL has no intrinsic unit; user confirms unscaled millimetres"},
            "step":{"path":str(step.resolve()),"sha256":hashlib.sha256(data).hexdigest(),
                    "unit_mm_explicit":bool(re.search(r"SI_UNIT\(\.MILLI\.,\.METRE\.\)",text)),
                    "solid_count":len(re.findall(r"MANIFOLD_SOLID_BREP\(",text)),
                    "named_solid_count":len(re.findall(r"MANIFOLD_SOLID_BREP\('[^']+'",text))},
            "navigation_geometry_verified":False,
            "unresolved":["assembled outer footprint including tires", "drive wheel axle midpoint", "LD06 laser scan origin and plane height"],
            "notes":"STEP vertex or control-point ranges are not exact BREP bounds. Do not infer electrical or wheel geometry from these ranges."}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("stl",type=Path);parser.add_argument("step",type=Path)
    args=parser.parse_args();print(json.dumps(inspect(args.stl,args.step),ensure_ascii=False,indent=2))
