from pathlib import Path
import json
import hashlib
import zipfile
import struct

HERE=Path(__file__).resolve().parent
OUT=HERE/'v1-fixed-front-wheels'
record=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
assert record['fcstd_reopened'] and record['exported_part_count']==15
assert all(s['valid'] and s['bounds_match'] for s in record['step_roundtrip'].values())
assert not record['critical_interferences']
viewer=json.loads((OUT/'viewer-verification.json').read_text(encoding='utf-8'))
assert viewer['file_uri_works'] and not viewer['console_errors']
g=(OUT/'EdgeMind_Assembly.glb').read_bytes()
magic,version,length=struct.unpack_from('<III',g)
assert magic==0x46546c67 and version==2 and length==len(g)
json_length,json_type=struct.unpack_from('<II',g,12)
assert json_type==0x4e4f534a
gltf=json.loads(g[20:20+json_length])
assert len(gltf['nodes'])==173
files=[p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.md','.json','.py','.cjs')]
files += [p for p in OUT.rglob('*') if p.is_file()
          and p.suffix not in ('.FCBak','.FCStd1','.FCStd2') and p.name!='preview-meshes.json']
manifest=[]
for p in sorted(files):
    if p.name=='package-manifest.json':continue
    manifest.append({'file':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,
                     'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
manifest_path=OUT/'package-manifest.json'
manifest_path.write_text(json.dumps({'units':'CAD: mm; GLB: m','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in files if p.name!='package-manifest.json']+[manifest_path]
archive=HERE/'EdgeMind_Chassis_v1.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(files):z.write(p,p.relative_to(HERE).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.infolist())==len(files)
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'files':len(files),
                  'CAD_valid':True,'STL_closed':15,'viewer_works':True,'GLB_header_valid':True},ensure_ascii=False))
