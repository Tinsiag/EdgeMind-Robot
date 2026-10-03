"""Remove only F1/F2/F3 and bridge their wire gaps in the native schematics.

Do not regenerate pages or write to the PCB. Keep a pre-edit snapshot for review.
"""
from pathlib import Path
import datetime, hashlib, json, shutil
from kicad_tools import parse, children, child, prop, apply_edits

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'review'
STEM = 'ProPrj_power_2026-10-02'
REMOVED = {'F1', 'F2', 'F3'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    backup = REVIEW / 'schematic-backups' / '2026-10-03-before-fuse-removal'
    assert not backup.exists(), 'Snapshot exists; review it before repeating this migration'
    backup.mkdir(parents=True)
    files = [ROOT / (n + '.kicad_sch') for n in
             [STEM, '01_power_input', '05_motor_left', '06_motor_right', '08_rail_protection']]
    sources = [REVIEW / n for n in ['redesign_budget.py', 'schematic_chinese.py',
                'schematic_overview.py', 'verify_redesign.py', 'redesign-components.json',
                '原理图修改说明_R2.md', 'redesign-verification.json']]
    for path in files + sources:
        shutil.copy2(path, backup / path.name)
    state = {'日期': datetime.datetime.now().isoformat(timespec='seconds'),
             'PCB_SHA256': sha(ROOT / (STEM + '.kicad_pcb')),
             'PROJECT_SHA256': sha(ROOT / (STEM + '.kicad_pro')),
             '原理图修改前哈希': {p.name: sha(p) for p in files},
             '操作': '删除板上F1、F2、F3；保留电子过流关断，入口保护依赖外部3S保护板'}
    (REVIEW / 'no-fuse-review-state.json').write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    input_note = ('Q1：漏极接电池输入，源极接保护后母线\n'
                  '电池端须有3S保护板：过流、短路及电芯保护。\n'
                  '本板不装保险丝；保护电流须匹配线束与铜箔。\n'
                  '瞬态抑制二极管不能把电压固定在17V以下。')
    motor_note = ('增益20，采样电阻20mΩ：约0.4V/A\n'
                  '输出滤波约1ms；母线过流阈值约3.04A\n'
                  '滤波关断不能替代入口快速短路保护\n'
                  '电池端保护板负责入口过流与短路切断')
    replacements = {
        '保险、防反接与电压窗口': '外部保护板、防反接与电压窗口',
        '本页连接来自真实层级引脚；子页保留跨模块同名网络。原电路板未同步，不能直接投板。':
        '电池端必须有过流、短路与电芯保护；本板不装保险丝。原电路板未同步，不能直接投板。',
        '输入：三串电池与外部电芯保护 / 保险丝与防反接':
        '输入：三串电池与外部保护板 / 防反接与母线储能',
        'Q1：漏极接电池输入，源极接保护后母线\n瞬态抑制二极管不能把电压固定在17V以下。\n保险丝额定值须匹配铜箔与线束承载能力。': input_note,
        '左电机：分支保险、电流监测与本地储能': '左电机：电子过流关断、电流监测与本地储能',
        '右电机：分支保险、电流监测与本地储能': '右电机：电子过流关断、电流监测与本地储能',
        '增益20，采样电阻20mΩ：约0.4V/A\n输出滤波约1ms；母线电流不同于绕组电流\n标称母线过流阈值约3.04A，须实测设定': motor_note,
        '分立过压关断方案用于控制成本；故障阶跃过冲和温升须实测。\n本方案不保证所有状态下阻断反灌，接入板卡仍须核对电源选择与隔离。\n母线过流阈值标称约3.04A；保险丝保护线束，不能代替绕组限流。':
        '分立过压关断方案用于控制成本；故障阶跃过冲和温升须实测。\n本方案不保证所有状态下阻断反灌，接入板卡仍须核对电源选择与隔离。\n母线过流阈值标称约3.04A；入口短路由电池保护板切断，模块限流仍须校准。',
    }
    bridges = {
        '01_power_input.kicad_sch': ('F1', 'b05177a1-3934-5e7d-98aa-a47acd1a31d5', 1, '72.39', '80.01'),
        '05_motor_left.kicad_sch': ('F2', '8356b445-ceab-51b0-9b65-787016007a81', 0, '49.53', '41.91'),
        '06_motor_right.kicad_sch': ('F3', '03272dfc-b265-5df2-8848-d4c46b4c9a89', 0, '49.53', '41.91'),
    }
    planned = []
    for path in files:
        text = path.read_bytes().decode('utf-8')
        sch = parse(text)
        edits = []
        if path.name in bridges:
            ref, wire_id, endpoint, old_x, new_x = bridges[path.name]
            fuse = [s for s in children(sch, 'symbol') if prop(s, 'Reference') == ref]
            assert len(fuse) == 1 and str(child(fuse[0], 'lib_id')[1]) == 'Device:Fuse'
            edits.append((fuse[0].start, fuse[0].end, ''))
            cached = [s for s in children(child(sch, 'lib_symbols'), 'symbol') if s[1] == 'Device:Fuse']
            assert len(cached) == 1
            edits.append((cached[0].start, cached[0].end, ''))
            wire = next(w for w in children(sch, 'wire') if child(w, 'uuid')[1] == wire_id)
            x = children(child(wire, 'pts'), 'xy')[endpoint][1]
            assert str(x) == old_x
            edits.append((x.start, x.end, new_x))
        for node in children(sch, 'text'):
            if str(node[1]) in replacements:
                atom = node[1]
                edits.append((atom.start, atom.end, json.dumps(replacements[str(atom)], ensure_ascii=False)))
        updated = apply_edits(text, edits)
        assert edits and '(face ' not in updated
        check = parse(updated)
        assert not (REMOVED & {prop(s, 'Reference') for s in children(check, 'symbol')})
        # Every retained symbol, wire, pin and component position is untouched,
        # except the single endpoint that now bridges each removed fuse.
        planned.append((path, text, updated, len(edits)))
    for path, text, updated, count in planned:
        assert path.read_bytes().decode('utf-8') == text, 'File changed after preparing edits'
        path.write_bytes(updated.encode('utf-8'))
        print(f'{path.name}: {count} targeted edits')
    meta_path = REVIEW / 'redesign-components.json'
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    assert {d['reference'] for d in metadata if d['reference'] in REMOVED} == REMOVED
    metadata = [d for d in metadata if d['reference'] not in REMOVED]
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PCB unchanged by this script:', sha(ROOT / (STEM + '.kicad_pcb')) == state['PCB_SHA256'])

if __name__ == '__main__':
    run()
