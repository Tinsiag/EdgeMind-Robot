"""Package V5 flat portrait display trial and verified CAD exports."""
from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
v=json.loads((HERE/'viewer-verification.json').read_text(encoding='utf-8'))
assert r['readback_verified'] and not r['critical_interferences']
assert not v['console_errors'] and v['third_layer_visibility_checked']
for name,key in [('LD06_LiDAR.STEP',r['lidar']['source_sha256']),('3D_PCB2_2026-10-20.step',r['perfboard']['source_sha256']),('MPU6050-V1_尺寸图.jpg',r['imu']['drawing_sha256'])]:
    assert hashlib.sha256((HERE/'references'/name).read_bytes()).hexdigest()==key
def included(p):
    return p.is_file() and '__pycache__' not in p.parts and p.name not in ('diagnose_roundtrip.py','roundtrip-diagnostics.json') and not p.name.startswith('package-manifest') and not any(c in p.name for c in ('.FCBak','.FCStd1','.FCStd2','.export.FCStd'))
files=sorted(p for p in HERE.rglob('*') if included(p))
entries=[{'path':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
(HERE/'package-manifest.json').write_text(json.dumps({'version':'V5 2026-10-21','files':entries},ensure_ascii=False,indent=2),encoding='utf-8')
files.append(HERE/'package-manifest.json')
target=HERE.parent/'EdgeMind_Chassis_v5_TouchDisplay.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,Path(HERE.name)/p.relative_to(HERE))
with zipfile.ZipFile(target) as z:assert z.testzip() is None
print(json.dumps({'zip':str(target),'bytes':target.stat().st_size,'files':len(files),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}),flush=True)
