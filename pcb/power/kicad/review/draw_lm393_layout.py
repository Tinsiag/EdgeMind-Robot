"""Draw a deterministic placement guide from the current native schematic netlist.

Creates SVG/notes only; it never edits the KiCad schematic or PCB.
"""
from pathlib import Path
from html import escape
import hashlib
import json
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review' / 'lm393-layout'
OUT.mkdir(exist_ok=True)
XML = ET.parse(ROOT / 'review' / 'lm393-layout-current.net.xml').getroot()
COMP = {c.get('ref'): c for c in XML.findall('components/comp')}
NET = {(n.get('ref'), n.get('pin')): net.get('name')
       for net in XML.findall('nets/net') for n in net.findall('node')}
PARTS = json.loads((ROOT / 'review' / 'lm393-layout-current-parts.json').read_text(encoding='utf-8'))
CURRENT = {c['位号']: c for c in PARTS['元件']}
PCB = ROOT / 'ProPrj_power_2026-10-02.kicad_pcb'
SCH = [ROOT / 'ProPrj_power_2026-10-02.kicad_sch', *sorted(ROOT.glob('0[1-9]_*.kicad_sch'))]
HASHES = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PCB, *SCH]}

GROUPS = [
    dict(ic='U22', cap='C102', lo=('R55', 'R56'), hi=('R57', 'R58'), pull='R59',
         output='BUCK_ENABLE', supply='VBAT_SYS', title='逻辑电源电压窗口',
         dest='至降压使能与逻辑电源开关', lower=9.00695),
    dict(ic='U23', cap='C103', lo=('R60', 'R61'), hi=('R62', 'R63'), pull='R64',
         output='MOTOR_POWER_OK', supply='+3V3', title='电机电源电压窗口',
         dest='至安全逻辑与过流检测输出', lower=9.65565),
]
for g in GROUPS:
    ic = g['ic']
    assert COMP[ic].findtext('value') == 'LM393BIDR'
    assert COMP[ic].findtext('footprint') == 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
    expected = {1: g['output'], 2: 'VREF_2V495', 4: 'GND',
                5: 'VREF_2V495', 7: g['output'], 8: 'VBAT_SYS'}
    for p, name in expected.items():
        assert NET[ic, str(p)] == name, (ic, p)
    for pin, pair in [(3, g['lo']), (6, g['hi'])]:
        top, bottom = pair
        assert NET[top, '1'] == 'VBAT_SYS'
        assert NET[top, '2'] == NET[bottom, '1'] == NET[ic, str(pin)]
        assert NET[bottom, '2'] == 'GND'
    assert NET[g['pull'], '1'] == g['supply']
    assert NET[g['pull'], '2'] == g['output']
    assert NET[g['cap'], '1'] == 'VBAT_SYS' and NET[g['cap'], '2'] == 'GND'
assert NET['U21', '1'] == NET['U21', '2'] == NET['R52', '2'] == 'VREF_2V495'
assert NET['U21', '3'] == 'GND' and NET['R52', '1'] == 'VBAT_SYS'

COL = dict(ink='#172c45', muted='#61758b', border='#d7e2ed', input='#dc8d18',
           output='#8c52cc', power='#d5475c', ref='#2478b3', ground='#228a65', pad='#e4b65a')
SCALE = 35.0
SVG = ['<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1420" viewBox="0 0 2000 1420">',
       '<defs><style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style></defs>']


def rect(x, y, w, h, fill, stroke='none', radius=0, width=1, dash=''):
    SVG.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" '
               f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" '
               f'stroke-dasharray="{dash}"/>')


def text(s, x, y, size=20, fill=None, anchor='start', weight=400):
    SVG.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" '
               f'fill="{fill or COL["ink"]}" text-anchor="{anchor}" font-weight="{weight}">{escape(str(s))}</text>')


def line(points, color, width=4, dash=''):
    pts = ' '.join(f'{x:.3f},{y:.3f}' for x, y in points)
    SVG.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
               f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}"/>')


def circle(x, y, r, fill, stroke='none', width=1):
    SVG.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')


def via(x, y, ground=True):
    c = COL['ground'] if ground else COL['ref']
    circle(x, y, 8, '#ffffff', c, 3)
    circle(x, y, 3, c)


def tag(s, x, y, color, anchor='start'):
    # Electrical labels stay ASCII and are separate from ordinary Chinese notes.
    assert s.isascii()
    text(s, x, y, 17, color, anchor, 600)


def passive(ref, cx, cy, reverse=False, caption='above', capacitor=False, caption_y=None):
    offset = (0.95 if capacitor else 0.825) * SCALE
    pw, ph = ((1.0, 1.45) if capacitor else (0.8, 0.95))
    p1 = (cx + offset if reverse else cx - offset, cy)
    p2 = (cx - offset if reverse else cx + offset, cy)
    for p, pt in [(1, p1), (2, p2)]:
        rect(pt[0] - pw*SCALE/2, pt[1] - ph*SCALE/2,
             pw*SCALE, ph*SCALE, COL['pad'], '#b18439', 2)
        text(p, pt[0], pt[1] + 5, 13, '#5c410f', 'middle', 700)
    bw, bh = ((1.25, 1.0) if capacitor else (1.0, 0.6))
    rect(cx-bw*SCALE/2, cy-bh*SCALE/2, bw*SCALE, bh*SCALE,
         '#a4b8c6' if capacitor else '#3e5060', '#253748', 2)
    value = COMP[ref].findtext('value').replace('/0.1%', '')
    if caption == 'above':
        text(ref+'  '+value, cx, caption_y if caption_y is not None else cy - 12 - ph*SCALE/2,
             18, anchor='middle', weight=600)
    else:
        text(ref+'  '+value, cx, cy + 26 + ph*SCALE/2, 18, anchor='middle', weight=600)
    return p1, p2


def soic(ref, cx, cy):
    rect(cx-3.9*SCALE/2, cy-4.9*SCALE/2, 3.9*SCALE, 4.9*SCALE,
         '#23374e', '#14243a', 6, 2)
    pins = {}
    for p in range(1, 9):
        dx = (-2.475 if p <= 4 else 2.475)*SCALE
        dy = ((p-1)*1.27-1.905 if p <= 4 else (8-p)*1.27-1.905)*SCALE
        x, y = cx+dx, cy+dy
        pins[p] = (x, y)
        rect(x-1.95*SCALE/2, y-0.6*SCALE/2, 1.95*SCALE, 0.6*SCALE,
             COL['pad'], '#b18439', 2)
        text(p, x, y+5, 15, '#5c410f', 'middle', 700)
    circle(cx-48, cy-70, 6, '#ffffff')
    text(ref, cx, cy+8, 24, '#ffffff', 'middle', 700)
    text('LM393B', cx, cy+40, 14, '#dceaf5', 'middle')
    for p, label in [(2, '−'), (3, '+'), (4, '地'),
                     (5, '+'), (6, '−'), (8, '供电')]:
        x, y = pins[p]
        text(label, cx + (-51 if p <= 4 else 51), y+5, 13, '#dceaf5',
             'start' if p <= 4 else 'end')
    return pins


rect(0, 0, 2000, 1420, '#f3f7fb')
text('U22 / U23 · LM393B 周边元件摆放示意', 55, 64, 38, weight=700)
text('顶层俯视；两颗统一为 1 脚朝左上，整组可旋转。相对摆放参考，具体间距以焊盘与设计规则为准。', 55, 109, 22, COL['muted'])

for index, g in enumerate(GROUPS):
    ox, oy = 50 + index*975, 150
    SVG.append(f'<g transform="translate({ox},{oy})">')
    rect(0, 0, 925, 790, '#ffffff', COL['border'], 18, 2)
    text(g['ic']+'  '+g['title'], 28, 47, 28, weight=700)
    text('上拉电阻 '+g['pull']+'：'+('电池保护后母线供电' if index == 0 else '板上 3.3V 供电'), 28, 84, 20, COL['muted'])
    rect(145, 272, 640, 308, '#eef8f3', '#d2ebdd', 14)
    text('连续地平面区域', 770, 574, 16, COL['ground'], 'end')
    cx, cy = 450, 410
    # Pad coordinates exactly match the assigned stock SOIC footprint, at 35 px/mm.
    pp = {p: (cx+(-2.475 if p <= 4 else 2.475)*SCALE,
              cy+((p-1)*1.27-1.905 if p <= 4 else (8-p)*1.27-1.905)*SCALE)
          for p in range(1, 9)}
    lo_mid = (248.875, pp[3][1])
    hi_mid = (647.125, pp[6][1])
    # Both open-collector outputs remain joined; route around the top of the group.
    line([pp[1], (302, pp[1][1]), (302, 230), (795, 230),
          (795, pp[7][1]), pp[7]], COL['output'])
    line([(419, 190), (438, 190), (438, 230)], COL['output'])
    circle(438, 230, 5, COL['output'])
    line([(795, 230), (860, 230)], COL['output'])
    text('1、7 脚共用输出', 548, 215, 16, COL['output'], 'middle')
    text(g['dest'], 864, 214, 16, COL['output'], 'end')
    line([(361.125, 190), (340, 190)], COL['power'])
    tag(g['supply'], 329, 195, COL['power'], 'end')
    # Input divider junctions stay on the two sides, next to pins 3 and 6.
    line([(248.875, 420), (248.875, 475)], COL['input'])
    line([lo_mid, pp[3]], COL['input'])
    circle(*lo_mid, 5, COL['input'])
    line([(647.125, 420), (647.125, 475)], COL['input'])
    line([hi_mid, pp[6]], COL['input'])
    circle(*hi_mid, 5, COL['input'])
    line([(191.125, 420), (176, 420)], COL['power'])
    tag('VBAT_SYS', 167, 426, COL['power'], 'end')
    line([(704.875, 420), (725, 420)], COL['power'])
    tag('VBAT_SYS', 736, 426, COL['power'])
    line([(191.125, 475), (174, 475)], COL['ground'])
    via(174, 475)
    tag('GND', 158, 481, COL['ground'], 'end')
    line([(704.875, 475), (735, 475)], COL['ground'])
    via(735, 475)
    tag('GND', 751, 481, COL['ground'])
    # Short reference stubs; the dashed distribution in the lower panel is conceptual.
    line([pp[2], (314, pp[2][1])], COL['ref'])
    circle(314, pp[2][1], 4, COL['ref'])
    tag('VREF_2V495', 313, 367, COL['ref'], 'end')
    line([pp[5], (593, pp[5][1]), (593, 534)], COL['ref'])
    circle(593, 534, 4, COL['ref'])
    tag('VREF_2V495', 593, 558, COL['ref'], 'middle')
    line([pp[4], (310, pp[4][1]), (310, 533)], COL['ground'])
    via(310, 533)
    tag('GND', 310, 559, COL['ground'], 'middle')
    # Each existing 100nF capacitor is adjacent to pin 8, with its own nearby ground via.
    line([pp[8], (571.75, pp[8][1]), (571.75, 292)], COL['power'])
    line([(571.75, 292), (525, 292)], COL['power'])
    tag('VBAT_SYS', 511, 298, COL['power'], 'end')
    line([(638.25, 292), (680, 292)], COL['ground'])
    via(680, 292)
    tag('GND', 696, 298, COL['ground'])
    passive(g['pull'], 390, 190, capacitor=False)
    passive(g['lo'][0], 220, 420)
    passive(g['lo'][1], 220, 475, reverse=True, caption='below')
    passive(g['hi'][0], 676, 420, reverse=True, caption_y=364)
    passive(g['hi'][1], 676, 475, caption='below')
    passive(g['cap'], 605, 292, capacitor=True)
    soic(g['ic'], cx, cy)
    text('① '+g['cap']+' 靠近 8 脚；电容地端与 4 脚分别就近下地。', 28, 624, 20)
    text('② '+ '/'.join(g['lo'])+' 靠近 3 脚；'+ '/'.join(g['hi'])+' 靠近 6 脚。', 28, 662, 20)
    text('③ 输出从上侧绕走，避开输入；走不开时以接地铜隔离。', 28, 700, 20)
    text('④ 标称电压窗口：约 '+f"{g['lower']:.2f}"+'～14.07 V。', 28, 738, 20)
    SVG.append('</g>')

rect(50, 975, 1900, 290, '#ffffff', COL['border'], 18, 2)
text('共享基准小组：U21 + R52', 78, 1019, 27, weight=700)
text('放在两组比较输入附近；分压下臂与基准共用连续地平面，避开电机与降压的大电流回流。', 78, 1056, 21, COL['muted'])
text('基准分配连接示意', 1860, 1019, 18, COL['muted'], 'end')
line([(881.125, 1135), (838, 1135)], COL['power'])
tag('VBAT_SYS', 824, 1142, COL['power'], 'end')
line([(938.875, 1135), (970, 1135), (970, 1101.75), (997.1875, 1101.75)], COL['ref'])
line([(970, 1135), (970, 1168.25), (997.1875, 1168.25)], COL['ref'])
circle(970, 1135, 5, COL['ref'])
line([(970, 1168.25), (970, 1213), (665, 1213)], COL['ref'], 3, '8 7')
line([(970, 1213), (1295, 1213)], COL['ref'], 3, '8 7')
tag('VREF_2V495', 970, 1246, COL['ref'], 'middle')
text('接 U22 的 2、5 脚', 649, 1220, 20, COL['ref'], 'end')
text('接 U23 的 2、5 脚', 1310, 1220, 20, COL['ref'])
line([(1062.8125, 1135), (1115, 1135)], COL['ground'])
via(1115, 1135)
tag('GND', 1132, 1142, COL['ground'])
passive('R52', 910, 1135)
rect(1030-22, 1135-51, 44, 102, '#23374e', '#14243a', 3)
for p, x, y in [(1, 997.1875, 1101.75), (2, 997.1875, 1168.25), (3, 1062.8125, 1135)]:
    rect(x-1.475*SCALE/2, y-0.6*SCALE/2, 1.475*SCALE, 0.6*SCALE, COL['pad'], '#b18439', 2)
    text(p, x, y+5, 14, '#5c410f', 'middle', 700)
text('U21', 1030, 1079, 21, anchor='middle', weight=700)
text('TL431BIDBZR', 1190, 1103, 20)
text('1、2 脚相连；3 脚接地', 1190, 1139, 19, COL['muted'])

legend = [('供电', 'power'), ('分压输入', 'input'), ('基准', 'ref'), ('共用输出', 'output'), ('地及地过孔', 'ground')]
for i, (name, color) in enumerate(legend):
    x = 78+i*305
    line([(x, 1310), (x+45, 1310)], COL[color], 5)
    text(name, x+59, 1317, 20, COL['muted'])
text('输入线与输出线不要长距离并行；地平面保持连续，不增加独立地网或在接地脚串电容。', 78, 1360, 21)
text('依据：TI SLCS005AH，第 3 页引脚定义、第 20 页布局；元件位号与连接取自当前原理图。2026-10-04', 78, 1396, 18, COL['muted'])
SVG.append('</svg>')
(OUT / 'U22_U23_布局示意.svg').write_text('\n'.join(SVG), encoding='utf-8')


def pad(ref, number):
    return next(p for p in CURRENT[ref]['焊盘'] if p['编号'] == str(number))


distances = {g['cap']: math.dist(pad(g['ic'], 8)['位置'], pad(g['cap'], 1)['位置']) for g in GROUPS}
rows = []
for g in GROUPS:
    rows.append(f"| {g['ic']} | {g['cap']} | {' / '.join(g['lo'])} | {' / '.join(g['hi'])} | {g['pull']} | "
                f"{'电池保护后母线' if g['supply']=='VBAT_SYS' else '板上3.3V'} |")
notes = f'''# U22 / U23 比较器摆放建议

2026-10-04。依据当前原理图的新导出网表和当前 PCB 读取结果制作，工程文件不作修改。

## 当前摆放的主要问题

- C102 的供电焊盘到 U22 的 8 脚中心直线距离约 {distances['C102']:.1f}mm；C103 到 U23 约 {distances['C103']:.1f}mm。这是焊盘中心距，实际走线可能更长。两颗去耦应分别移到各自的供电脚旁，不能将两颗电容集中在远处。
- U22 的四颗分压电阻已经在输入附近，主要检查接地点、基准走线和输出隔离；U23 的 R60～R63 还在芯片下方较远位置，建议按示意图组成两对并移近相应输入脚。
- 当前 PCB 的 U22 为 0°、U23 为 90°。示意图为了便于对照引脚，两颗均画为 0°，允许整组旋转；旋转后以真实焊盘编号为准。图中不是原 PCB 的坐标或已通过 DRC 的布线方案。

## 按真实位号摆放

| 芯片 | 就近去耦 | 欠压分压：靠3脚 | 过压分压：靠6脚 | 输出上拉 | 上拉电源 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

每颗芯片的 2、5 脚均接同一基准，4 脚接地，8 脚接电池保护后母线；1、7 脚是开集电极输出，在当前电路中相连。两颗芯片的输出属于不同网络，不能彼此相连。U23 的输出还与电机过流比较器 U30 共用，保持当前原理图连接。

低端分压电阻的 1 脚与高端电阻的 2 脚组成采样点，直接短接到对应输入。高端电阻的 1 脚接被测母线，低端电阻的 2 脚就近接连续地平面。分压中点不铺大面积铜，不走长线，不贴着降压开关节点或电机 PWM 线走。

摆放优先级是去耦、输入分压、共享基准，再安排输出上拉。我的布线目标是去耦与 8 脚之间约 1～2mm 的短连接、分压点至输入约 2～3mm；这些是本板的布局目标，并非 TI 的硬性距离限制。应同时满足焊盘间距、装配庭院和可制造规则。电容地端与芯片 4 脚分别就近落到同一个连续地平面，不把地脚经电容再接地。

U21 和 R52 放在两组比较输入附近，R52 的 2 脚接 U21 的 1、2 脚，U21 的 3 脚接地。基准与分压下臂的地应避免承载电机、泄放和降压电源的大电流回流；沿同一连续地平面实现，不另建浮地，也不为了模拟地划分而割断回流路径。

输出优先沿芯片外侧绕走，不与反相输入长距离平行。若必须靠近，使用连接到连续地平面的地铜或接地走线隔开。输出上拉保留原电源域：R59 上拉到电池保护后母线，R64 上拉到板上3.3V，不能统一改接。

## 手册依据与检查边界

[TI 官方 LM393B 手册 SLCS005AH](https://www.ti.com/lit/ds/symlink/lm393.pdf)，第 3 页图4-1和表4-1、第 20 页7.2.4、7.2.5及图7-4。手册要求供电去耦、抑制输出到反相输入的耦合、输入电阻贴近器件；没有规定芯片必须朝向哪个方向。当前窗口检测没有迟滞，良好布局能减少耦合，但不能代替后续电压边界抖动测试或必要的迟滞设计。

示意图仅使用现有器件，不新增阻容。彩色线表达连接与走线方向，地过孔是 PCB 工艺示意。所有器件、引脚和电源域均已与当前原生网表逐项核对；未对主 PCB 移件或重新布线。

矢量图：`U22_U23_布局示意.svg`；预览：`U22_U23_布局示意.png`。
'''
(OUT / 'U22_U23_布局说明.md').write_text(notes, encoding='utf-8')
checks = {
    '日期': '2026-10-04', '手册': 'https://www.ti.com/lit/ds/symlink/lm393.pdf',
    '网表逐脚校验': True, '图中实物位号': ['U21','R52',*[r for g in GROUPS for r in [g['ic'],g['cap'],*g['lo'],*g['hi'],g['pull']]]],
    '现有去耦焊盘中心距离_mm': distances,
    '原理图与PCB_SHA256': HASHES, '主工程只读': True,
    '说明': '图为确定性SVG示意；SOIC、0603、0805和SOT23按现有封装焊盘尺寸绘制，不是完成布线的PCB。'
}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in HASHES.items())
(OUT / '绘图核验.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'输出目录': str(OUT), '主PCB未修改': True, '实际器件数量': len(checks['图中实物位号']),
                  '当前去耦距离_mm': distances}, ensure_ascii=False))
