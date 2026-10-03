"""Read-only verification of the F1 holder binding and preserved PCB geometry."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew
from kicad_tools import parse, children, child, prop
from sync_pcb_from_schematic import geometry

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'review'
STEM = 'ProPrj_power_2026-10-02'
state = json.loads((REVIEW / 'f1-board-review-state.json').read_text(encoding='utf-8'))
backup = Path(state['备份目录'])
path = ROOT / (STEM + '.kicad_pcb')
before = pcbnew.LoadBoard(str(backup / path.name))
after = pcbnew.LoadBoard(str(path))
old = {f.GetReference(): f for f in before.GetFootprints()}
fps = {f.GetReference(): f for f in after.GetFootprints()}
assert len(old) == 210 and len(fps) == 211 and set(fps) == set(old) | {'F1'}
for ref, fp in old.items():
    assert geometry(fp) == geometry(fps[ref]), (ref, 'Existing geometry changed')
xml = ET.parse(REVIEW / 'redesign.net.xml').getroot()
comps = {c.get('ref'): c for c in xml.findall('components/comp')}
nets = {(n.get('ref'), n.get('pin')): net.get('name')
        for net in xml.findall('nets/net') for n in net.findall('node')}
checked = 0
changed = []
for ref, fp in fps.items():
    assert str(fp.GetFPID().GetLibNickname()) + ':' + str(fp.GetFPID().GetLibItemName()) == comps[ref].findtext('footprint'), ref
    paths = {comps[ref].find('sheetpath').get('tstamps').rstrip('/') + '/' + stamp
             for stamp in comps[ref].findtext('tstamps').split()}
    assert fp.GetPath().AsString() in paths, (ref, 'Schematic link mismatch')
    for pad in fp.Pads():
        if pad.GetNumber():
            checked += 1
            assert pad.GetNetname() == nets[ref, pad.GetNumber()], (ref, pad.GetNumber())
    if ref in old:
        oldpins = {p.m_Uuid.AsString(): p.GetNetname() for p in old[ref].Pads()}
        for pad in fp.Pads():
            previous = oldpins[pad.m_Uuid.AsString()]
            if previous != pad.GetNetname():
                changed.append([ref, pad.GetNumber(), previous, pad.GetNetname()])
assert len(changed) == 2 and {p[0] for p in changed} == {'CN1', 'Q1'}
f1 = fps['F1']
pads = list(f1.Pads())
assert len(pads) == 4 and sorted(p.GetNumber() for p in pads) == ['1', '1', '2', '2']
positions = {(pad.GetNumber(), tuple(pcbnew.ToMM(pad.GetFPRelativePosition()))) for pad in pads}
assert positions == {('1', (0.0, 0.0)), ('1', (0.0, 3.4)), ('2', (9.92, 0.0)), ('2', (9.92, 3.4))}
assert all(tuple(pcbnew.ToMM(pad.GetDrillSize())) == (1.78, 1.78) for pad in pads)
assert nets['CN1', '2'] == nets['F1', '1']
assert nets['F1', '2'] == nets['Q1', '2']
assert nets['F1', '1'] != nets['F1', '2'], 'Fuse bypassed'
models = [m.m_Filename for m in f1.Models()]
assert models
for model in models:
    assert Path(model.replace('${KICAD10_3DMODEL_DIR}', 'D:/KiCad/10.0/share/kicad/3dmodels')).is_file()
drc = json.loads((REVIEW / 'f1-board-drc.json').read_text(encoding='utf-8'))
assert not drc['schematic_parity']
assert hashlib.sha256((ROOT / (STEM + '.kicad_pro')).read_bytes()).hexdigest() == state['PROJECT_SHA256']
sch = parse((ROOT / '01_power_input.kicad_sch').read_bytes().decode('utf-8'))
symbol = next(n for n in children(sch, 'symbol') if prop(n, 'Reference') == 'F1')
report = {
    '日期': datetime.now().isoformat(timespec='seconds'), '备份目录': str(backup),
    '修改前PCB_SHA256': state['PCB_SHA256'],
    '修改后PCB_SHA256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'F1封装': 'Fuse:Fuseholder_Blade_Mini_Keystone_3568', 'F1板载': True,
    'F1原理图UUID': str(child(symbol, 'uuid')[1]), '板上元件数': len(fps),
    '原有210个元件位置与方向及焊盘几何保留': True,
    'F1位置毫米': list(pcbnew.ToMM(f1.GetPosition())), 'F1模型': models,
    '输入连接': 'CN1.2 -> F1.1; F1.2 -> Q1.2', '原有焊盘网络调整': changed,
    '逐个核对有编号焊盘数': checked, '原理图一致性问题数': len(drc['schematic_parity']),
    '现有设计规则违规数': len(drc['violations']), '未连接项目数': len(drc['unconnected_items']),
    '项目配置未修改': True, '保险片购买链接': prop(symbol, '购买链接'),
    '保险座购买参考': prop(symbol, '保险座参考链接'), '保险座原厂图纸': prop(symbol, '保险座数据手册'),
    '保险座焊孔': '中心距9.92×3.40mm，钻孔1.78mm，1/1与2/2各为同一电气端',
    '采购边界': '封装按3568标准四孔；国产同孔位保险座尚未定型，不将01530008.J直接认作兼容。',
}
(REVIEW / 'f1-board-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
