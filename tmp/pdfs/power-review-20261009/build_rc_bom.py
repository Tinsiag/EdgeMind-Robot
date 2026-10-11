import html
import json
import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'power-diagnostics' / '电阻电容_交互BOM_2026-10-09.html'
bom = json.loads((BASE / 'interactive-bom-extracted.json').read_text(encoding='utf-8'))
preview = json.loads((BASE / 'interactive-pcb-preview.json').read_text(encoding='utf-8'))
components = {c['des']: c for g in bom['designator_info'] for c in g['top'] + g['bottom']}
specs = {}

def add(refs, value, package, rating, role, note='', issue=False, original=''):
    for ref in refs.split(','):
        specs[ref] = dict(ref=ref, kind=ref[0], value=value, package=package,
                          rating=rating, role=role, note=note, issue=issue,
                          original=original or '与建议标称值一致')

add('R1,R6', '10Ω', '0603', '1% · ≥0.1W', '自举串联电阻',
    '正确值为 10Ω。原 HTML 显示 10R、底层 Value 却是 10K。用户已确认实装 10Ω。', True, '显示 10R / Value 10K')
add('R2,R11', '82kΩ', '0603', '1% · ≥0.1W', '输出反馈上臂',
    '与下臂 11.1kΩ 配对，标称输出约 5.03V。请核对实装值及反馈通路；原 BOM 的 100kΩ 与 11.1kΩ 配对会设定约 6V。', True, '显示 82K / Value 100K')
add('R3,R12', '11.1kΩ', '0603', '1% · ≥0.1W', '输出反馈下臂，接 GND',
    '本表统一采用上臂 82kΩ、下臂 11.1kΩ。若改用原厂 100kΩ 上臂，必须将下臂一起改为 13.7kΩ。')
add('R4,R5,R8,R9', '10kΩ', '0603', '1% · ≥0.1W', 'USB-C CC 上拉，宣告 3A',
    '每个 CC 引脚经独立 10kΩ 拉到本路 5V。原库料号对应 56kΩ，宣告电流不同；CC 电阻不会提高实际输出能力。', True, '显示 10kΩ / 库料号为 56kΩ')
add('R7,R13', '300kΩ', '0603', '1% · ≥0.1W', 'EN 分压上臂，接 VCCIN',
    '与 130kΩ 配合完成降压器使能；不能作为 3S 电池欠压保护。')
add('R10,R14', '130kΩ', '0603', '1% · ≥0.1W', 'EN 分压下臂，接 GND')
add('R15', '10kΩ', '0603', '1% · ≥0.1W', 'VM 指示 LED 限流',
    'R15 必须为 10kΩ。原 HTML 共用的名称/描述残留 10R，请与 R1、R6 的 10Ω 分开配料。', True, 'Value 10K / 名称与描述 10R')

add('C1,C2,C3,C8,C9,C10', '22µF', '0805', '≥25V · X5R/X7R', '降压输入去耦',
    '原选型为 22µF/25V X5R。每路输入 3 颗；还需核对 12.6V 下有效容量和电容组纹波温升。')
add('C4,C5,C12,C13', '22µF', '0805', '建议25V · X5R/X7R', '5V 输出滤波',
    '现板每路 2 颗。建议带载改进时每路就近补 1 颗合适的 22µF，并验证有效容量、纹波及负载阶跃；新增电容不在本表 35 件内。')
add('C6,C14', '100nF', '0603', '≥16V · X7R', '自举电容',
    '100nF = 0.1µF。推荐使用 25V 或 50V X7R。注意与 220pF、1µF 两组 0603 电容分开。')
add('C7,C15', '220pF', '0603', '推荐50V · C0G/NP0', '反馈前馈电容，跨反馈上臂',
    '实际容量必须为 220pF；原厂亦有 X7R 选型。原 HTML 的 100nF 描述错误，两者相差约 455 倍。', True, 'Value 220pF / 描述 100nF')
add('C11,C16', '1µF', '0603', '≥10V · X7R/X5R', '芯片内部 VCC 旁路',
    '实际容量为 1µF，推荐 25V；原 HTML 的 100nF 描述错误。VCC 正常工作时约 3.5V。', True, 'Value 1µF / 描述 100nF')
add('C58', '100µF*', '0805', '≥25V · 需改装/核实', '输入母线储能',
    '100µF 为储能选型起点，原 0805 缺完整型号与耐压，尚未确认合格。建议采用 ≥25V 低 ESR 电解/聚合物并改封装或外接。修板可在原焊盘装 22µF/25V 陶瓷，另以短连接在 VCCIN/GND 间加 100µF/25V 储能电容；电解正极接 VCCIN、负极接 GND。最终容量需按实板瞬态验证。', True, '100µF / 0805 / 型号与耐压未知')
add('C59', '10µF', '0805', '≥25V · X5R/X7R', '输入母线去耦',
    '原 BOM 未指定完整型号和耐压，应按 ≥25V 器件核对。', True, '10µF / 耐压未填写')
add('C60,C61', '100nF', '0805', '推荐50V · X7R', '输入母线高频去耦', '100nF = 0.1µF；至少 25V，推荐 50V。')

assert set(specs) == {ref for ref in components if re.fullmatch(r'[RC]\d+', ref)}
assert len(specs) == 35
SCALE = 100 / 25.4  # PREVIEW 单位为 10mil；BOM ec 坐标为 mm。
for ref, item in specs.items():
    ec = components[ref]['ec']
    assert components[ref]['ft_name'] == ('R' if ref[0] == 'R' else 'C') + item['package']
    item['x'] = ec['x'] * SCALE
    item['y'] = -ec['y'] * SCALE
    item['angle'] = -ec['ang']
    item['width'] = ec['dx'] * SCALE
    item['height'] = ec['dy'] * SCALE
    assert all(math.isfinite(item[k]) for k in ['x', 'y', 'angle', 'width', 'height'])
    if ref == 'R15':
        item['module'] = '指示灯'
    elif ref in ['C58', 'C59', 'C60', 'C61']:
        item['module'] = '输入母线'
    elif ref in ['R1','R2','R3','R4','R5','R7','R10','C1','C2','C3','C4','C5','C6','C7','C11']:
        item['module'] = 'USB3 · U5'
    else:
        item['module'] = 'USB4 · U1'

def n(v):
    return f'{v:.5f}'.rstrip('0').rstrip('.') or '0'

def geometry(g, filled=False):
    if not g:
        return ''
    if g[0] == 'CIRCLE':
        return f'<circle cx="{n(g[1])}" cy="{n(-g[2])}" r="{n(g[3])}"/>'
    if g[0] == 'R':
        _, x, y, w, h, angle, rx, ry = g
        return f'<rect width="{n(w)}" height="{n(h)}" rx="{n(rx)}" ry="{n(ry)}" transform="translate({n(x)} {n(-y)}) rotate({n(-angle)})"/>'
    x, y = g[0:2]
    parts = [f'M {n(x)} {n(-y)}']
    i = 2
    while i < len(g):
        token = g[i]
        if token == 'L':
            i += 1
            continue
        if token == 'ARC':
            angle, ex, ey = g[i+1:i+4]
            sine = abs(math.sin(math.radians(angle)/2))
            radius = math.hypot(ex-x, ey-y) / (2*sine) if sine > 1e-9 else 0
            if radius:
                parts.append(f'A {n(radius)} {n(radius)} 0 {int(abs(angle)>180)} {int(angle>0)} {n(ex)} {n(-ey)}')
            else:
                parts.append(f'L {n(ex)} {n(-ey)}')
            x, y = ex, ey
            i += 4
            continue
        ex, ey = g[i:i+2]
        parts.append(f'L {n(ex)} {n(-ey)}')
        x, y = ex, ey
        i += 2
    if filled:
        parts.append('Z')
    return '<path d="' + ' '.join(parts) + '"/>'

layers = []
# 仅用源文件几何生成定位底图，不执行原 HTML 的程序。
for layer, color, fill in [(48, '#819095', False), (12, '#b3bdc1', True), (7, '#c7d0d3', True), (3, '#596e74', False), (11, '#30474d', False)]:
    shapes = []
    for row in preview:
        if row[0] not in ['FILL', 'POLY'] or row[4] != layer:
            continue
        if row[0] == 'FILL':
            shapes.extend(geometry(g, True) for g in row[7])
        else:
            shape = geometry(row[6])
            shapes.append(f'<g stroke-width="{n(row[5])}">{shape}</g>')
    layers.append(f'<g fill="{color if fill else "none"}" stroke="{color}" stroke-width="0.18">' + ''.join(shapes) + '</g>')

data = sorted(specs.values(), key=lambda d: (d['kind'] != 'R', int(d['ref'][1:])))
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
template = (BASE / 'rc_bom_template.html').read_text(encoding='utf-8')
page = template.replace('__PCB_SVG__', ''.join(layers)).replace('__RC_DATA__', payload)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding='utf-8')
print(json.dumps({'path': str(OUT), 'components': len(data), 'resistors': 15, 'capacitors': 20, 'size_bytes': OUT.stat().st_size, 'board_paths': sum(1 for row in preview if row[0] == 'POLY' and row[4] == 3)}, ensure_ascii=False))
