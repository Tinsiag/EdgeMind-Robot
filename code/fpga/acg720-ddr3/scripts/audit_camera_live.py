from pathlib import Path
import hashlib, json, re
root=Path(__file__).resolve().parents[1]
base=root/'.local/framebuffer-first/ch38-camera-bars'
live=root/'.local/framebuffer-first/ch38-camera-live'
differences=[]
for old in (base/'src').rglob('*'):
    if old.is_file():
        new=live/'src'/old.relative_to(base/'src')
        assert new.exists(),new
        if old.read_bytes()!=new.read_bytes():
            differences.append(old.relative_to(base/'src').as_posix())
assert sorted(differences)==['ov5640_ctrl.v','ov5640_init_table_rgb.v'],differences
for name,before,after in [('ov5640_ctrl.v',"default: verify_value=8'h80;","default: verify_value=8'h00;"),
                         ('ov5640_init_table_rgb.v',"24'h503D_80","24'h503D_00")]:
    assert (base/'src'/name).read_text(encoding='utf-8').replace(before,after)==(live/'src'/name).read_text(encoding='utf-8')
report=(live/'impl/pnr/ch38_camera_live_tr_content.html').read_text(encoding='utf-8')
setup=re.search(r'Numbers of Setup Violated Endpoints</td>\s*<td>(\d+)</td>',report).group(1)
hold=re.search(r'Numbers of Hold Violated Endpoints</td>\s*<td>(\d+)</td>',report).group(1)
fs=live/'impl/pnr/ch38_camera_live.fs'
record=dict(sha256=hashlib.sha256(fs.read_bytes()).hexdigest().upper(),
    differences_from_verified_colorbars=differences,setup_violated_endpoints=int(setup),
    hold_violated_endpoints=int(hold),timing_signed_off=False)
(live/'build-audit-20261008.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
