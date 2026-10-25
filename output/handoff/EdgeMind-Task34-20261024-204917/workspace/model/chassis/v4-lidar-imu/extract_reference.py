"""Inspect the supplied LD06 CAD without guessing its mounting geometry."""
from pathlib import Path
import json, hashlib
import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
path = HERE / 'references/LD06_LiDAR.STEP'
shape = Part.read(str(path))
def xyz(v): return [round(float(a), 8) for a in v]
def bounds(s):
    b = s.optimalBoundingBox(False, False)
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]
data = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bounds': bounds(shape), 'solids': []}
for si, solid in enumerate(shape.Solids):
    faces = []
    for fi, f in enumerate(solid.Faces):
        surf = f.Surface
        if isinstance(surf, Part.Cylinder):
            faces.append({'face': fi, 'type': 'cylinder', 'radius': surf.Radius,
                          'center': xyz(surf.Center), 'axis': xyz(surf.Axis), 'bounds': bounds(f), 'area': f.Area})
        elif isinstance(surf, Part.Plane) and f.Area > 20:
            faces.append({'face': fi, 'type': 'plane', 'center': xyz(f.CenterOfMass),
                          'normal': xyz(f.normalAt(0, 0)), 'bounds': bounds(f), 'area': f.Area})
    data['solids'].append({'index': si, 'bounds': bounds(solid), 'valid': solid.isValid(),
                            'volume': solid.Volume, 'faces': faces})
(HERE/'reference-extraction.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
print(json.dumps(data, indent=2), flush=True)
