"""Synchronize this R2 PCB without moving or regenerating existing footprints.

Run with KiCad's Python. The native KiCad 10 PCB stores net names on pads.
Only the three obsolete fuse footprints, changed pad nets, and XT60's model
reference require edits. All other board content is retained byte for byte.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

import pcbnew
from kicad_tools import parse, children, child, prop, apply_edits

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'review'
STEM = 'ProPrj_power_2026-10-02'
BOARD = ROOT / (STEM + '.kicad_pcb')
NETLIST = REVIEW / 'pcb-sync-current.net.xml'
STOCK = Path('D:/KiCad/10.0/share/kicad')
MODEL_NAME = 'AMASS_XT60PW-M_1x02_P7.20mm_Horizontal.step'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp_id(fp):
    return str(fp.GetFPID().GetLibNickname()) + ':' + str(fp.GetFPID().GetLibItemName())


def geometry(fp):
    return {
        'uuid': fp.m_Uuid.AsString(),
        'position': [fp.GetPosition().x, fp.GetPosition().y],
        'orientation': fp.GetOrientationDegrees(),
        'layer': fp.GetLayer(),
        'locked': fp.IsLocked(),
        'pads': sorted((
            p.GetNumber(), p.m_Uuid.AsString(), p.GetPosition().x, p.GetPosition().y,
            p.GetSize().x, p.GetSize().y, p.GetDrillSize().x, p.GetDrillSize().y,
            p.GetOrientationDegrees(), p.GetShape(), p.GetAttribute(), p.GetLayerSet().FmtBin(),
        ) for p in fp.Pads()),
    }


def run():
    original = BOARD.read_bytes()
    text = original.decode('utf-8')
    tree = parse(text)
    assert str(child(tree, 'version')[1]) == '20260206'
    board = pcbnew.LoadBoard(str(BOARD))
    assert not list(board.GetTracks()) and not list(board.Zones())
    xml = ET.parse(NETLIST).getroot()
    components = {
        c.get('ref'): c for c in xml.findall('components/comp')
        if c.find("property[@name='exclude_from_board']") is None
    }
    excluded = {
        c.get('ref') for c in xml.findall('components/comp')
        if c.find("property[@name='exclude_from_board']") is not None
    }
    footprints = {prop(f, 'Reference'): f for f in children(tree, 'footprint')}
    assert len(components) == 210 and excluded == {'F1'}
    assert set(footprints) - set(components) == {'F1', 'F2', 'F3'}
    assert not (set(components) - set(footprints))
    desired_nets = {
        (p.get('ref'), p.get('pin')): n.get('name')
        for n in xml.findall('nets/net') for p in n.findall('node')
        if p.get('ref') in components
    }

    before_geometry = {
        fp.GetReference(): geometry(fp) for fp in board.GetFootprints()
        if fp.GetReference() in components
    }
    edits = []
    net_changes = []
    model_changes = []
    pad_count = 0
    for ref, node in footprints.items():
        if ref not in components:
            edits.append((node.start, node.end, ''))
            continue
        c = components[ref]
        assert str(node[1]) == c.findtext('footprint'), (ref, 'footprint mismatch')
        assert prop(node, 'Value') == c.findtext('value'), (ref, 'value mismatch')
        # A multi-unit symbol contributes several UUIDs; any corresponding unit
        # is a valid board link. Preserve the currently selected unit path.
        sheet_path = c.find('sheetpath').get('tstamps')
        valid_paths = {sheet_path + stamp for stamp in c.findtext('tstamps').split()}
        assert str(child(node, 'path')[1]) in valid_paths, (ref, 'symbol link mismatch')
        lib, name = str(node[1]).split(':', 1)
        libfile = (
            ROOT / (lib + '.pretty') if lib == 'EdgeMind_Module'
            else STOCK / 'footprints' / (lib + '.pretty')
        ) / (name + '.kicad_mod')
        library = parse(libfile.read_text(encoding='utf-8'))
        pad_numbers = {str(p[1]) for p in children(node, 'pad') if str(p[1])}
        stock_numbers = {str(p[1]) for p in children(library, 'pad') if str(p[1])}
        symbol_numbers = {p.get('num') for p in c.findall('units/unit/pins/pin')}
        assert pad_numbers == stock_numbers == symbol_numbers, (ref, 'pin/pad mismatch')
        for pad in children(node, 'pad'):
            pin = str(pad[1])
            if not pin:
                continue
            expected = desired_nets[(ref, pin)]
            net = child(pad, 'net')
            assert net is not None
            pad_count += 1
            if str(net[1]) != expected:
                net_changes.append({'位号': ref, '焊盘': pin, '原网络': str(net[1]), '新网络': expected})
                edits.append((net[1].start, net[1].end, json.dumps(expected, ensure_ascii=False)))
        for model in children(node, 'model'):
            modelpath = Path(str(model[1]).replace('${KICAD10_3DMODEL_DIR}', str(STOCK / '3dmodels'))
                             .replace('${KIPRJMOD}', str(ROOT)))
            assert modelpath.is_file(), (ref, modelpath)
            if ref == 'CN1':
                assert modelpath.name == MODEL_NAME
                portable = '${KIPRJMOD}/3dmodels/' + MODEL_NAME
                edits.append((model[1].start, model[1].end, json.dumps(portable)))
                model_changes.append({'位号': ref, '旧路径': str(model[1]), '新路径': portable,
                                      '说明': '同一完整七实体模型，改为项目内路径，变换不变'})

    assert len(net_changes) == 5, net_changes
    assert len(model_changes) == 1
    updated = apply_edits(text, edits).encode('utf-8')
    target_model = ROOT / '3dmodels' / MODEL_NAME
    source_model = REVIEW / 'stock-model-supplement' / MODEL_NAME
    assert source_model.is_file()
    if target_model.exists():
        assert sha(target_model) == sha(source_model), 'Preserve an existing different model'

    backup = REVIEW / 'pcb-sync-backups' / datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    for path in [BOARD, ROOT / (STEM + '.kicad_pro'), ROOT / 'README.md',
                 REVIEW / '原理图修改说明_R2.md', REVIEW / 'stock-model-supplement' / 'README.md',
                 ROOT / (STEM + '.kicad_sch'), *sorted(ROOT.glob('0[1-9]_*.kicad_sch'))]:
        shutil.copy2(path, backup / path.name)
    assert BOARD.read_bytes() == original, 'Board changed while checking; reload and reconcile'
    if not target_model.exists():
        shutil.copy2(source_model, target_model)
    temporary = REVIEW / 'pcb-sync-candidate.kicad_pcb'
    temporary.write_bytes(updated)
    candidate = pcbnew.LoadBoard(str(temporary))
    new_footprints = {f.GetReference(): f for f in candidate.GetFootprints()}
    assert set(new_footprints) == set(components)
    for ref, fp in new_footprints.items():
        assert geometry(fp) == before_geometry[ref], (ref, 'Existing geometry changed')
        assert fp_id(fp) == components[ref].findtext('footprint')
        for p in fp.Pads():
            if p.GetNumber():
                assert p.GetNetname() == desired_nets[(ref, p.GetNumber())]
    assert not list(candidate.GetTracks()) and not list(candidate.Zones())
    assert BOARD.read_bytes() == original, 'Board changed before commit; preserve current board'
    BOARD.write_bytes(updated)
    report = {
        '日期': datetime.now().isoformat(timespec='seconds'),
        'KiCad版本': pcbnew.Version(), '备份目录': str(backup),
        '修改前PCB_SHA256': hashlib.sha256(original).hexdigest(),
        '修改后PCB_SHA256': sha(BOARD),
        '原理图网表_SHA256': sha(NETLIST),
        '修改前封装数': len(footprints), '修改后封装数': len(new_footprints),
        '删除板上封装': ['F1', 'F2', 'F3'], '新增封装': [],
        '原有封装库标识已一致': 210,
        'KiCad自带封装': 208, 'AT8236双排排母自建封装': 2,
        '核对有编号的焊盘数': pad_count,
        '网络修改': net_changes, '模型修改': model_changes,
        '现有元件位置方向锁定状态及焊盘几何完整保留': True,
        '走线数': 0, '铜区数': 0, '板框状态': '尚未设置',
        '同步范围': '封装、原理图关联、焊盘网络、模型；未实施布局布线',
    }
    (REVIEW / 'pcb-sync-verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
