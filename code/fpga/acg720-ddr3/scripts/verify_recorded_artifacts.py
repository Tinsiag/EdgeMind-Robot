from pathlib import Path
import hashlib, json, re
root=Path(__file__).resolve().parents[1]
rows=[('ch38-frame-test','ch38_frame_test','0x000041A4'),
      ('ch38-camera-bars','ch38_camera_bars','0x00004FCF'),
      ('ch38-camera-live','ch38_camera_live','0x0000AF89')]
for folder,name,code in rows:
    project=root/'.local/framebuffer-first'/folder
    record=json.loads((project/'verified-result-20261008.json').read_text(encoding='utf-8'))
    fs=project/'impl/pnr'/f'{name}.fs'
    digest=hashlib.sha256(fs.read_bytes()).hexdigest().upper()
    assert record['sha256'].upper()==digest,(folder,'SHA mismatch')
    assert record['user_code'].upper()==code.upper(),folder
    log=root/'.local/logs'/f'{folder}-program-20261008.log'
    # Static and camera logs use the same folder names as their projects.
    data=log.read_text(encoding='utf-8',errors='replace')
    assert f'User Code is: {code}' in data and '0x70026020' in data,folder
    assert (record.get('user_confirmed') is True or
            record.get('confirmed_by_user') is True or
            record.get('result','').startswith('User confirmed complete')),record
    print(f'PASS artifact identity, successful SRAM log, user LED result: {folder} {code}')
docs=['README.md','DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md',
      'FRAMEBUFFER-TEST-RESULT-2026-10-08.md','CAMERA-FRAME-TEST-2026-10-08.md',
      'LEGACY-DDR-DIAGNOSIS-2026-10-08.md','FRAMEBUFFER-FIRST-PLAN-2026-10-08.md']
for name in docs:
    path=root/name
    text=path.read_text(encoding='utf-8')
    assert text.count('```')%2==0,(name,'unclosed code fence')
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if not target.startswith(('http:','https:')):
            assert (path.parent/target.split('#')[0]).exists(),(name,target)
print('PASS document links and code fences')
assert "24'h503D_00" in (root/'.local/framebuffer-first/ch38-camera-live/src/ov5640_init_table_rgb.v').read_text(encoding='utf-8')
assert "default: verify_value=8'h00;" in (root/'.local/framebuffer-first/ch38-camera-live/src/ov5640_ctrl.v').read_text(encoding='utf-8')
print('PASS current scene test has color bars disabled and readback verifies disabled state')
