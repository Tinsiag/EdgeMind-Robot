from pathlib import Path
import json,hashlib,zipfile,struct

HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
v=json.loads((HERE/'viewer-verification.json').read_text(encoding='utf-8'))
assert r['fcstd_reopened'] and r['exploded_native_verified']
assert all(x['valid'] and x['closed'] for x in r['step_roundtrip'].values())
assert not r['critical_interferences'] and all(x['closed'] for x in r['stl_files'].values())
assert r['feature_measurements']['measured_plate_thicknesses_mm']=={'LowerTray':5,'UpperDeck':5}
assert r['feature_measurements']['camera_STEP_valid']
assert all(abs(x['measured_open_area_mm2']-x['expected_area_mm2'])<.001 for x in r['feature_measurements']['measured_motor_openings'])
assert v['file_uri_works'] and not v['console_errors']
assert all(p['lift']==65 for p in v['exploded']['upper_parts'])
assert any(p['name']=='CameraBracket' for p in v['exploded']['upper_parts'])
g=(HERE/'EdgeMind_Assembly.glb').read_bytes();magic,version,length=struct.unpack_from('<III',g)
assert magic==0x46546c67 and version==2 and length==len(g)
jn,jt=struct.unpack_from('<II',g,12);assert jt==0x4e4f534a
glb=json.loads(g[20:20+jn]);assert len(glb['nodes'])==len(r['parts'])
files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
       and p.suffix not in ('.FCBak','.FCStd1','.FCStd2','.bak','.zip')
       and p.name not in ('preview-meshes.json','package-manifest.json')
       and '.styled.' not in p.name and '.export.' not in p.name]
manifest=[{'file':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]
mp=HERE/'package-manifest.json';mp.write_text(json.dumps({'units':'CAD mm; GLB m','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
files.append(mp)
archive=HERE.parent/'EdgeMind_Chassis_v3_Camera.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(files):z.write(p,Path(HERE.name)/p.relative_to(HERE))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files),
 'STEP_solids':r['step_roundtrip']['EdgeMind_Assembly.step']['solids'],
 'closed_STL':len(r['stl_files']),'upper_members':r['upper_assembly_verified']['members'],'browser_errors':v['console_errors']},ensure_ascii=False))
