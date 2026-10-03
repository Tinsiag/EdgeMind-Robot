"""Restore ASCII electrical names without rebuilding sheets or PCB footprints."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import pcbnew
from kicad_tools import parse, Node, children, child, prop, apply_edits
from schematic_chinese import LEGACY_NETS
from sync_pcb_from_schematic import geometry

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'review'
STEM = 'ProPrj_power_2026-10-02'
CLI = 'D:/KiCad/10.0/bin/kicad-cli.exe'
q = lambda s: json.dumps(s, ensure_ascii=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def exported(path):
    subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    '--output', str(path), str(ROOT / (STEM + '.kicad_sch'))], cwd=ROOT, check=True)
    return ET.parse(path).getroot()


def partitions(xml):
    return {frozenset((p.get('ref'), p.get('pin')) for p in net.findall('node')): net.get('name')
            for net in xml.findall('nets/net')}


def run():
    before = exported(REVIEW / 'before-ascii-nets.net.xml')
    old_parts = partitions(before)
    assert '地' in old_parts.values() and 'GND' not in old_parts.values(), 'Already migrated; do not rerun'
    board_path = ROOT / (STEM + '.kicad_pcb')
    board_bytes = board_path.read_bytes()
    board = pcbnew.LoadBoard(str(board_path))
    before_geometry = {f.GetReference(): geometry(f) for f in board.GetFootprints()}
    backup = REVIEW / 'pcb-sync-backups' / datetime.now().strftime('%Y-%m-%d_%H%M%S-before-ascii-nets')
    backup.mkdir(parents=True, exist_ok=False)
    sheets = [ROOT / (STEM + '.kicad_sch'), *sorted(ROOT.glob('0[1-9]_*.kicad_sch'))]
    for path in [board_path, ROOT / (STEM + '.kicad_pro'), ROOT / 'README.md', *sheets,
                 REVIEW / 'redesign.net.xml', REVIEW / 'redesign-erc.json',
                 REVIEW / 'redesign-verification.json', REVIEW / 'footprint-model-audit.json',
                 REVIEW / '原理图修改说明_R2.md', REVIEW / 'PCB同步说明_R2.md',
                 REVIEW / '电源板原理图_R2.pdf', REVIEW / '电源板接口线序_R2.csv',
                 REVIEW / 'before-ascii-nets.net.xml']:
        if path.is_file(): shutil.copy2(path, backup / path.name)
    state = {'操作': '恢复ASCII网络名与GND并排除网络名中文化', 'PCB_SHA256': sha(board_path),
             'PROJECT_SHA256': sha(ROOT / (STEM + '.kicad_pro')), '备份目录': str(backup)}
    (REVIEW / 'ascii-net-review-state.json').write_text(q(state), encoding='utf-8')
    reverse = {value: name for name, value in LEGACY_NETS.items()}
    tree = ast.parse((REVIEW / 'schematic_overview.py').read_text(encoding='utf-8'))
    assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'configs' for t in n.targets))
    configs = ast.literal_eval(assignment.value)
    aliases = {c[0] + '.kicad_sch': {alias: net for net, alias, _, _ in c[6]} for c in configs}
    text_changes = {
        '逻辑板5V_稳压输出 / 5.10V / 供电目标3A': '逻辑板降压输出 / 5.10V / 供电目标3A',
        '计算板5V_稳压输出 / 5.10V / 供电目标3A': '计算板降压输出 / 5.10V / 供电目标3A',
        '5V过压关断 / 标称约5.364V / 逻辑板5V_保护输出': '逻辑板供电过压关断 / 标称约5.364V',
        '5V过压关断 / 标称约5.364V / 计算板5V_保护输出': '计算板供电过压关断 / 标称约5.364V',
    }
    changes = []
    for path in sheets:
        original = path.read_bytes()
        text = original.decode('utf-8')
        sch = parse(text)
        edits = []
        def rename(atom, name, kind):
            if str(atom) != name:
                changes.append({'文件': path.name, '类型': kind, '原名称': str(atom), '新名称': name})
                edits.append((atom.start, atom.end, q(name)))
        for kind in ('label', 'global_label', 'hierarchical_label'):
            for node in children(sch, kind):
                old = str(node[1])
                new = aliases.get(path.name, {}).get(old, old) if kind == 'hierarchical_label' else reverse.get(old, old)
                if old == '电池正极':
                    new = 'BAT_POS'
                    if kind == 'label':
                        edits.append((node[0].start, node[0].end, 'global_label'))
                        edits.append((node[1].end, node[1].end, ' (shape passive)'))
                assert new.isascii(), (path.name, kind, new)
                rename(node[1], new, kind)
        for sheet in children(sch, 'sheet'):
            file = prop(sheet, 'Sheetfile')
            for pin in children(sheet, 'pin'):
                name = aliases[file][str(pin[1])]
                rename(pin[1], name, 'sheet_pin')
        for symbol in children(sch, 'symbol'):
            if child(symbol, 'lib_id')[1] == 'power:GND':
                value = next(p for p in children(symbol, 'property') if p[1] == 'Value')
                rename(value[2], 'GND', 'ground_power_name')
        for note in children(sch, 'text'):
            if str(note[1]) in text_changes:
                rename(note[1], text_changes[str(note[1])], 'ordinary_description')
        assert path.read_bytes() == original, 'Preserve concurrent schematic changes'
        path.write_bytes(apply_edits(text, edits).encode('utf-8'))
    after = exported(REVIEW / 'redesign.net.xml')
    new_parts = partitions(after)
    assert set(old_parts) == set(new_parts), 'Electrical connections changed'
    assert len(old_parts) == len(new_parts)
    assert {c.get('ref') for c in before.findall('components/comp')} == {c.get('ref') for c in after.findall('components/comp')}
    mapping = {old_parts[pins]: new_parts[pins] for pins in old_parts}
    assert len(set(mapping.values())) == len(mapping), 'Network names merged'
    assert all(name.isascii() and '?' not in name for name in mapping.values())
    assert mapping['地'] == 'GND'
    desired = {(n.get('ref'), n.get('pin')): net.get('name') for net in after.findall('nets/net') for n in net.findall('node')}
    text = board_bytes.decode('utf-8')
    tree = parse(text)
    edits = []
    changed_pads = []
    for fp in children(tree, 'footprint'):
        ref = prop(fp, 'Reference')
        for pad in children(fp, 'pad'):
            pin = str(pad[1])
            if not pin: continue
            current = str(child(pad, 'net')[1])
            assert mapping[current] == desired[ref, pin], (ref, pin, 'Existing PCB differs electrically')
            if current != desired[ref, pin]: changed_pads.append([ref, pin, current, desired[ref, pin]])
    def walk(n):
        if isinstance(n, Node):
            yield n
            for c in n:
                if isinstance(c, Node): yield from walk(c)
    for node in walk(tree):
        if node and node[0] == 'net':
            atom = node[-1]
            old = str(atom)
            if old in mapping and mapping[old] != old: edits.append((atom.start, atom.end, q(mapping[old])))
    candidate = backup / 'ASCII-net-candidate.kicad_pcb'
    candidate.write_bytes(apply_edits(text, edits).encode('utf-8'))
    updated = pcbnew.LoadBoard(str(candidate))
    fps = {f.GetReference(): f for f in updated.GetFootprints()}
    assert set(fps) == set(before_geometry)
    checked = 0
    for ref, fp in fps.items():
        assert geometry(fp) == before_geometry[ref], (ref, 'PCB geometry changed')
        for pad in fp.Pads():
            if pad.GetNumber():
                checked += 1
                assert pad.GetNetname() == desired[ref, pad.GetNumber()]
    assert len(updated.GetTracks()) == len(board.GetTracks()) and len(updated.Zones()) == len(board.Zones())
    assert board_path.read_bytes() == board_bytes, 'PCB changed before commit; preserve concurrent changes'
    board_path.write_bytes(candidate.read_bytes())
    assert sha(ROOT / (STEM + '.kicad_pro')) == state['PROJECT_SHA256']
    report = {'日期': datetime.now().isoformat(timespec='seconds'), '备份目录': str(backup),
              '修改前PCB_SHA256': state['PCB_SHA256'], '修改后PCB_SHA256': sha(board_path),
              '网络数量': len(new_parts), '网络重命名数量': sum(a != b for a, b in mapping.items()),
              '改名焊盘数量': len(changed_pads), '核对有编号物理焊盘数量': checked,
              '板上元件数量': len(fps), '整个网表电气连接分组保持不变': True,
              'PCB元件位置方向UUID与焊盘几何保持不变': True, '项目配置未修改': True,
              'GND有编号物理焊盘数量': sum(p.GetNetname() == 'GND' for f in fps.values() for p in f.Pads()),
              '电气网络名全部ASCII': True, '网络名问号数量': 0, '旧名到新名': mapping,
              '原理图标签与说明修改': changes,
              '说明': '电气名称不参加中文翻译；功能说明保留中文默认字体；普通说明不直接插入网络标识。'}
    (REVIEW / 'ascii-net-verification.json').write_text(q(report), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('旧名到新名', '原理图标签与说明修改')}, ensure_ascii=False, indent=2))


if __name__ == '__main__': run()
