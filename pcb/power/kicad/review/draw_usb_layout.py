"""Draw the 38 parts on 02_usb_5v as four PCB placement groups; never save the board."""
from pathlib import Path
from html import escape
import ast
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import pcbnew
from kicad_tools import parse, children, prop

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review'/'usb-layout'
OUT.mkdir(exist_ok=True)
NAME='两路5V与USB供电_布局示意'
PCB=ROOT/'ProPrj_power_2026-10-02.kicad_pcb'
SOURCES=[PCB,*sorted(ROOT.glob('*.kicad_sch'))]
HASHES={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
XML=ET.parse(ROOT/'review'/'usb-schematic-current.net.xml').getroot()
COMP={c.get('ref'):c for c in XML.findall('components/comp')}
NET={(n.get('ref'),n.get('pin')):net.get('name')
     for net in XML.findall('nets/net') for n in net.findall('node')}
BOARD=pcbnew.LoadBoard(str(PCB))
FP={f.GetReference():f for f in BOARD.GetFootprints()}
SHEET=parse((ROOT/'02_usb_5v.kicad_sch').read_bytes().decode('utf-8'))
REFS={prop(c,'Reference') for c in children(SHEET,'symbol') if not prop(c,'Reference').startswith('#')}
COL=dict(ink='#172d45',muted='#62788e',edge='#d5e2ed',fab='#5a7087',court='#a8b9c8',
         pad='#e8bb64',power='#d54c5d',gate='#d0861d',enable='#8850bd',ref='#287bbb',ground='#23875f')
SVG=['<svg xmlns="http://www.w3.org/2000/svg" width="2800" height="2050" viewBox="0 0 2800 2050">',
     '<defs><style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style></defs>']

# Reuse only drawing definitions. Do not import or execute the earlier artifact generator.
helper_path=ROOT/'review'/'draw_input_layout.py'
helper_source=helper_path.read_text(encoding='utf-8')
allowed={'rect','text','line','circle','tag','arrow','Group'}
definitions=[ast.get_source_segment(helper_source,n)
             for n in ast.parse(helper_source).body
             if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in allowed]
assert len(definitions)==len(allowed)
helper='\n\n'.join(definitions)
helper=helper.replace("14,'#4f3814'","12 if len(p.GetNumber()) > 2 else 14,'#4f3814'")
exec(compile(helper,str(helper_path)+':drawing-definitions','exec'),globals())

CHANNELS=[
    dict(title='逻辑板供电',buck='U5',ind='L1',cin=['C1','C2','C3'],cout=['C4','C5'],
         rb='R1',cb='C6',cv='C11',rt='R2',rl='R3',cf='C7',
         usb='U7',connector='USB1',ui='C104',uo='C105',iset='R65',pull='R66',
         raw='+5V_FPGA',protected='+5V_FPGA_PROT',vbus='USB1_VBUS',fault='USB1_FAULT_PULSE_N'),
    dict(title='计算板供电',buck='U1',ind='L2',cin=['C8','C9','C10'],cout=['C12','C13'],
         rb='R6',cb='C14',cv='C16',rt='R11',rl='R12',cf='C15',
         usb='U8',connector='USB2',ui='C106',uo='C107',iset='R67',pull='R68',
         raw='+5V_AI',protected='+5V_AI_PROT',vbus='USB2_VBUS',fault='USB2_FAULT_PULSE_N'),
]
PLAN={}
for i,g in enumerate(CHANNELS):
    PLAN[f'降压{i}']={g['buck']:(12,10,0),g['ind']:(4.2,14.5,180),
        g['cin'][0]:(7,5,180),g['cin'][1]:(7,7.3,180),g['cin'][2]:(7,9.6,180),
        g['cout'][0]:(2,19.5,0),g['cout'][1]:(6,19.5,0),
        g['rb']:(13.1375,13.4,-90),g['cb']:(10.6,14.5,180),g['cv']:(16.8,11.4,0),
        g['rt']:(17,6.6,-90),g['rl']:(17,9.025,0),g['cf']:(19.5,6.6,-90)}
    PLAN[f'端口{i}']={g['usb']:(13,11.5,90),g['connector']:(13,4,180),
        g['ui']:(9,13.9,180),g['uo']:(8.7,10.2,180),
        g['iset']:(15.7,14.65,-90),g['pull']:(5.5,8.3,0)}
assert {r for group in PLAN.values() for r in group}==REFS
assert len(REFS)==38
CURRENT={}
for ref in REFS:
    f=FP[ref]
    assert f.GetFPID().GetLibItemName()==COMP[ref].findtext('footprint').split(':',1)[1],ref
    pads=[]
    for p in f.Pads():
        if p.GetNumber(): assert p.GetNetname()==NET[ref,p.GetNumber()],(ref,p.GetNumber())
        pads.append(dict(pin=p.GetNumber(),net=p.GetNetname(),
                         position=[pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)]))
    CURRENT[ref]=dict(position=[pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)],
                      angle=f.GetOrientationDegrees(),value=COMP[ref].findtext('value'),pads=pads,
                      footprint=COMP[ref].findtext('footprint'))

# Verify all electrical groupings, including the off-page overvoltage protection.
for g in CHANNELS:
    u=g['buck'];v=g['usb'];b='Net-('+u+'-'
    for pin,name in {1:'GND',2:'VLOGIC_IN',3:b+'SW)',4:'GND',5:b+'BST)',
                     6:'BUCK_ENABLE',7:b+'VCC)',8:b+'FB)'}.items(): assert NET[u,str(pin)]==name
    assert NET[g['ind'],'1']==NET[u,'3'] and NET[g['ind'],'2']==g['raw']
    assert NET[g['rb'],'1']==NET[u,'5'] and NET[g['rb'],'2']==NET[g['cb'],'1']
    assert NET[g['cb'],'2']==NET[u,'3']
    assert NET[g['cv'],'1']==NET[u,'7'] and NET[g['cv'],'2']=='GND'
    for c in g['cin']: assert NET[c,'1']=='VLOGIC_IN' and NET[c,'2']=='GND'
    for c in g['cout']: assert NET[c,'1']==g['raw'] and NET[c,'2']=='GND'
    assert NET[g['rt'],'1']==NET[g['cf'],'1']==g['raw']
    assert NET[g['rt'],'2']==NET[g['cf'],'2']==NET[g['rl'],'1']==NET[u,'8']
    assert NET[g['rl'],'2']=='GND'
    assert NET[v,'1']==g['protected'] and NET[v,'8']==g['vbus'] and g['raw']!=g['protected']
    assert NET[g['ui'],'1']==g['protected'] and NET[g['uo'],'1']==g['vbus']
    assert NET[g['ui'],'2']==NET[g['uo'],'2']==NET[v,'2']=='GND'
    assert NET[g['iset'],'1']==NET[v,'3'] and NET[g['iset'],'2']=='GND'
    assert NET[g['pull'],'1']=='+3V3' and NET[g['pull'],'2']==NET[v,'7']==g['fault']
    assert NET[v,'6']==NET[g['connector'],'A5']
    assert NET[v,'5']==NET[g['connector'],'B5']
    assert NET[g['connector'],'A9']==NET[g['connector'],'B9']==g['vbus']
    assert NET[g['connector'],'A12']==NET[g['connector'],'B12']==NET[g['connector'],'SH']=='GND'
    assert NET[v,'4'].startswith('unconnected-')


def connection(group,points,kind='power',width=3,dash=''):
    coords=[group.pin(p[0],p[1]) if isinstance(p[0],str) else group.pt(*p) for p in points]
    line(coords,COL[kind],width,dash)


def label_at(group,ref,point,caption=None,size=19,anchor='middle'):
    text(caption or ref,*group.pt(*point),size,anchor=anchor,weight=600)


rect(0,0,2800,2050,'#f3f7fb')
text('02_usb_5v · 两路降压与 USB-C 供电的 PCB 摆放',55,66,40,weight=700)
text('顶层俯视；38 个实际元件、原封装焊盘与编号。各小组分别放大；彩线是连接提示，未代替整板布线或热设计。',55,113,23,COL['muted'])
ALL_GROUPS={}
for index,g in enumerate(CHANNELS):
    y=155+index*800
    rect(50,y,1260,770,'#fff',COL['edge'],18,2)
    text(g['title']+'：'+g['buck']+' + '+g['ind']+' 降压核心',78,y+47,28,weight=700)
    text('保持两路外围元件各自成组；输入在左上、电感在左下，反馈放右上。',78,y+86,21,COL['muted'])
    B=Group(f'降压{index}',105,y+145,26)
    ALL_GROUPS[f'降压{index}']=B
    rect(*B.pt(-.7,2.3),24.1*26,20.3*26,'#edf7f1','#d3e9dc',14)
    # A small switching-copper region, shown only as a relative-placement hint.
    rect(*B.pt(7.2,10.1),3.1*26,5.35*26,'#fff3df','#e8c88c',10)
    for c in g['cin']:
        connection(B,[(8.8,3.0),(8.8,PLAN[f'降压{index}'][c][1]),(c,1)],width=3)
        B.ground(c,2,(4.8,PLAN[f'降压{index}'][c][1]))
    connection(B,[(8.8,9.6),(g['buck'],2)],width=4)
    tag('VLOGIC_IN',*B.pt(8.8,2.0),COL['power'],'middle')
    connection(B,[(g['buck'],3),(9.65,10.325),(9.65,14.5),(g['cb'],2),(g['ind'],1)],'gate',4)
    connection(B,[(g['buck'],5),(g['rb'],1)],'gate')
    connection(B,[(g['rb'],2),(g['cb'],1)],'gate')
    connection(B,[(g['ind'],2),(0,14.5),(0,18.4),(22,18.4)],width=4)
    for c in g['cout']:
        p=B.pin(c,1)
        connection(B,[((p[0]-B.ox)/B.scale,18.4),(c,1)],width=3)
        B.ground(c,2,(PLAN[f'降压{index}'][c][0]+.95,20.6))
    tag(g['raw'],*B.pt(22,17.4),COL['power'],'end')
    text('送往过压保护',*B.pt(22,19.7),18,COL['power'],'end')
    arrow(*B.pt(22,18.4),1,0,COL['power'])
    # A separate sense route from the output capacitor node, away from switching copper.
    connection(B,[(5.05,18.4),(21.7,18.4),(21.7,3.2),(15.3,3.2),(15.3,5.775),(g['rt'],1)],'ref',2.5,'6 4')
    connection(B,[(20.7,3.2),(20.7,5.825),(g['cf'],1)],'ref',2.5,'6 4')
    connection(B,[(g['rt'],2),(17,8.3),(16.175,8.3),(g['rl'],1),(g['buck'],8)],'ref')
    connection(B,[(g['cf'],2),(19.5,8.3),(16.175,8.3)],'ref')
    B.ground(g['rl'],2,(19.5,9.025))
    connection(B,[(g['buck'],7),(15.85,9.675),(g['cv'],1)],'power')
    B.ground(g['cv'],2,(19.5,11.4))
    B.ground(g['buck'],1,(11.55,8.4))
    B.ground(g['buck'],4,(11.8,11.9))
    connection(B,[(g['buck'],6),(14.4,10.325),(14.4,17.3),(17.5,17.3)],'enable')
    tag('BUCK_ENABLE',*B.pt(17.5,16.5),COL['enable'],'middle')
    B.draw()
    for c in g['cin']:
        py=B.pt(7,PLAN[f'降压{index}'][c][1])[1]
        text(c,127,py-5,20,weight=700)
        text('22µF / 25V',127,py+20,16,COL['muted'])
    text(g['buck'],*B.pt(12,10.25),20,anchor='middle',weight=700)
    label_at(B,g['ind'],(4.2,14.0),size=25)
    text('4.7µH',*B.pt(4.2,15.3),18,COL['muted'],'middle')
    for c in g['cout']: label_at(B,c,(PLAN[f'降压{index}'][c][0],21.55),c+' 22µF',17)
    for ref,caption,x in [(g['rt'],'82.5k',17),(g['cf'],'220pF',19.5)]:
        label_at(B,ref,(x,4.0),size=19)
        text(caption,*B.pt(x,4.95),15,COL['muted'],'middle')
    label_at(B,g['rl'],(22,9.25),g['rl']+' 11k',18,'start')
    label_at(B,g['cv'],(22.5,12.5),g['cv']+' 1µF',18,'start')
    line([B.pt(22.2,12.2),B.pt(17.5,11.4)],COL['muted'],1.1)
    label_at(B,g['rb'],(16,14.6),g['rb']+' 10Ω',18)
    label_at(B,g['cb'],(10.6,16.3),g['cb']+' 100nF',18)
    tag('GND',*B.pt(21.5,20.8),COL['ground'],'middle')
    text('同一连续地平面',*B.pt(21.5,21.8),16,COL['ground'],'middle')
    points=[
        ('先放芯片和最靠近的输入电容',[g['cin'][-1]+' 靠近 2 脚输入与 4 脚地。','另外两颗输入电容顺着输入铜排开。']),
        ('电感靠近 3 脚开关输出',[g['ind']+' 的 1 脚接开关，2 脚接输出。','橙色区域保持紧凑，避开反馈回路。']),
        ('自举和内部供电各自贴近',[g['rb']+'/'+g['cb']+' 靠 5 脚与 3 脚。',g['cv']+' 靠 7 脚并就近下地。']),
        ('反馈放在另一侧',[g['rt']+'/'+g['rl']+'/'+g['cf']+' 靠 8 脚。','从输出电容处单独引回反馈取样。']),
        ('两路保持相同的布局思路',['整组可以旋转或平移。','输入共享，两个 5V 输出各自独立。']),
    ]
    for j,(head,rows) in enumerate(points):
        py=y+175+j*105
        text(head,832,py,22,weight=700)
        for k,row in enumerate(rows):text(row,832,py+30+k*27,19,COL['muted'])
    text('先锁定关键回路，再安排外部保护和连接器；图片中的铜区与线条只表达摆放意图。',78,y+750,20)

    # Explicitly preserve the real off-page protection, not a direct buck-to-USB link.
    rect(1338,y+285,223,184,'#f8f9fc',COL['edge'],12,2,'8 5')
    text('08 页',1449,y+325,24,anchor='middle',weight=700)
    text('过压保护',1449,y+363,25,anchor='middle',weight=700)
    text('降压输出先保护',1449,y+404,18,COL['muted'],'middle')
    text('再进入 USB 控制器',1449,y+433,18,COL['muted'],'middle')
    line([(1313,y+376),(1332,y+376)],COL['power'],4)
    arrow(1332,y+376,1,0,COL['power'])
    line([(1565,y+376),(1582,y+376)],COL['power'],4)
    arrow(1582,y+376,1,0,COL['power'])

    rect(1590,y,1160,770,'#fff',COL['edge'],18,2)
    text(g['usb']+' / '+g['connector']+'：控制器与接口小组',1618,y+47,28,weight=700)
    text('HUSB305-02 + 六针供电口；接口朝向板外，配置线分开连接。',1618,y+86,21,COL['muted'])
    U=Group(f'端口{index}',1690,y+155,32)
    ALL_GROUPS[f'端口{index}']=U
    rect(*U.pt(4,8.9),15.5*32,9*32,'#edf7f1','#d3e9dc',14)
    connection(U,[(g['ui'],1),(g['usb'],1)],width=4)
    connection(U,[(g['ui'],1),(7.0,13.9)],width=3)
    tag(g['protected'],*U.pt(7.0,12.8),COL['power'],'end')
    connection(U,[(g['usb'],8),(g['uo'],1)],width=4)
    connection(U,[(g['uo'],1),(10.0,8.9),(g['connector'],'A9')],width=3)
    # The second VBUS contact and CC2 require routing/layer choices on the final board.
    connection(U,[(g['usb'],8),(g['connector'],'B9')],width=2.5,dash='7 5')
    connection(U,[(g['usb'],6),(g['connector'],'A5')],'ref',3)
    connection(U,[(g['usb'],5),(g['connector'],'B5')],'ref',2.5,'6 4')
    connection(U,[(g['usb'],3),(13.325,13.8),(g['iset'],1)],'gate')
    connection(U,[(g['usb'],7),(12.675,9.2),(6.325,9.2),(g['pull'],2)],'enable')
    connection(U,[(g['pull'],1),(3.3,8.3)],'power')
    tag('+3V3',*U.pt(3.3,7.2),COL['power'],'middle')
    connection(U,[(6.325,9.2),(4.0,9.2),(4.0,10.25)],'enable')
    tag(g['fault'],*U.pt(6.1,10.95),COL['enable'],'end')
    U.ground(g['ui'],2,(6.6,13.9))
    U.ground(g['uo'],2,(6.8,10.2))
    U.ground(g['usb'],2,(11.3,13.5))
    U.ground(g['iset'],2,(15.7,16.8))
    # Shell contacts and both USB ground contacts remain connected to the same ground net.
    for pin,endpoint in [('A12',(9.5,8.0)),('B12',(16.5,8.0))]: U.ground(g['connector'],pin,endpoint)
    for pos in U.pins[g['connector']]['SH']:
        circle(pos[0],pos[1],4,'none',COL['ground'],1.6)
    U.draw()
    label_at(U,g['connector'],(13,3.5),size=25)
    text('USB4125-GF-A',*U.pt(13,4.8),16,COL['muted'],'middle')
    text('插口朝板外',*U.pt(13,-.7),20,COL['power'],'middle')
    line([U.pt(13,-.2),U.pt(13,.65)],COL['power'],3)
    arrow(*U.pt(13,-.2),0,-1,COL['power'])
    text(g['usb'],*U.pt(13,11.7),22,anchor='middle',weight=700)
    label_at(U,g['ui'],(9,16.1),g['ui']+' 1µF',19)
    label_at(U,g['uo'],(8.7,11.8),g['uo']+' 4.7µF',19)
    label_at(U,g['iset'],(15.7,17.6),g['iset']+' 150k',19)
    label_at(U,g['pull'],(5.5,6.6),g['pull']+' 10k',19)
    tag('GND',*U.pt(18.7,17.0),COL['ground'],'middle')
    for j,(head,rows) in enumerate([
        ('接口与控制器相邻',['VBUS 的两脚都接电源。','CC1 与 CC2 分别连接，不能并接。']),
        ('输入与输出电容分开',[g['ui']+' 靠 1 脚输入。',g['uo']+' 靠 8 脚输出与接口后侧。']),
        ('限流电阻收近控制器',[g['iset']+' 接 3 脚并就近下地。','4 脚为未用脚，保持未连接。']),
        ('故障输出上拉到 3.3V',[g['pull']+' 靠 7 脚状态输出。','连到逻辑侧，避开降压开关铜区。']),
        ('外壳与接口地就近接地',['保持同一地平面与短回流。','交叉的提示线在 PCB 中分层绕线。']),
    ]):
        py=y+175+j*105
        text(head,2335,py,22,weight=700)
        for k,row in enumerate(rows):text(row,2335,py+30+k*27,19,COL['muted'])
    text('配置线与电源交叉时，可用过孔换层；本图实线和虚线均为连接提示。',1618,y+750,20)

rect(50,1790,2700,204,'#fff',COL['edge'],18,2)
text('整板摆放顺序：降压完整小组 → 各自过压保护 → USB 控制器 → 板边接口',78,1838,28,weight=700)
for x,label,kind in [(80,'电源连接','power'),(470,'开关与自举','gate'),(930,'使能与故障输出','enable'),
                     (1460,'反馈与接口配置','ref'),(2000,'同一地平面','ground')]:
    line([(x,1880),(x+48,1880)],COL[kind],4)
    text(label,x+62,1887,21,COL[kind])
text('MP2236 的输入、地回路应短而宽；反馈元件靠近芯片并远离开关区域。不要将两路独立输出直接并联。',78,1928,23)
text('示意采用现有封装；虚线装配边界不含全部插拔和散热空间。最终需检查铜宽、温升、装配、走线与整板设计规则。',78,1968,21,COL['muted'])
text('依据原生原理图、PCB 和厂商手册核对 · 仅新增布局参考 · 四个小组可整体旋转与平移',55,2030,20,COL['muted'])
SVG.append('</svg>')
(OUT/(NAME+'.svg')).write_text('\n'.join(SVG),encoding='utf-8')
for zoom_name,box,width in [
    ('两路降压核心_放大图','50 155 1260 1570',1260),
    ('两路USB端口_放大图','1590 155 1160 1570',1160),
]:
    zoom_svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="1570" viewBox="{box}">',*SVG[1:]]
    (OUT/(zoom_name+'.svg')).write_text('\n'.join(zoom_svg),encoding='utf-8')

# Independent, conservative native courtyard-box check inside every suggested group.
COURTS={}
for group in PLAN:
    boxes={}
    for ref in PLAN[group]:
        pts=[]
        for s in FP[ref].GraphicalItems():
            if s.GetLayer()!=pcbnew.F_CrtYd:continue
            b=s.GetBoundingBox()
            pts.extend([(pcbnew.ToMM(b.GetLeft()),pcbnew.ToMM(b.GetTop())),
                        (pcbnew.ToMM(b.GetRight()),pcbnew.ToMM(b.GetBottom()))])
        boxes[ref]=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]
    for i,a in enumerate(boxes):
        for b in list(boxes)[i+1:]:
            ax,ay,ar,ab=boxes[a];bx,by,br,bb=boxes[b]
            assert min(ar,br)<=max(ax,bx) or min(ab,bb)<=max(ay,by),(group,a,b,'courtyard')
    COURTS[group]=boxes
for path,h in HASHES.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,(path,'source changed')

audit=dict(元件数=len(REFS),元件=CURRENT,分组绘图坐标=PLAN,装配边界包围盒=COURTS,
           本组装配边界包围盒重叠=False,原理图与PCB焊盘网络核对='通过',
           原文件SHA256=HASHES,原文件修改=False,
           说明='38 个现有元件；独立小组的相对布局；尚未布线、未核验整板与机壳冲突或热性能')
(OUT/'绘图核验.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
notes='''# 两路 5V 与 USB 供电的 PCB 布局说明

本图按用户确认的 PCB 布局用途绘制，使用 02_usb_5v 页的全部 38 个实际元件。元件轮廓、装配边界、焊盘几何与编号读取当前原生 PCB，连接按当前原理图导出的网络表核对。两路各含一个 13 元件降压小组、一个 6 元件 USB 小组，图中小组分别放大，坐标不代表整板最终放置。

## 两条完整供电链

| 用途 | 降压核心 | 输入电容 | 输出电容 | 自举 | 内部供电 | 反馈 | USB 控制与接口 |
|---|---|---|---|---|---|---|---|
| 逻辑板 | U5、L1 | C1、C2、C3 | C4、C5 | R1、C6 | C11 | R2、R3、C7 | U7、USB1、C104、C105、R65、R66 |
| 计算板 | U1、L2 | C8、C9、C10 | C12、C13 | R6、C14 | C16 | R11、R12、C15 | U8、USB2、C106、C107、R67、R68 |

两路降压输出各自先送到 08_rail_protection 页的过压保护，再返回本页各自的 USB 控制器输入。不要把降压输出直接连接到 USB 控制器而绕过保护；两路 5V 输出也不直接并联。公共输入可共享一条足够宽的输入铜，输入电容、开关电流和输出电容回路仍应在各自小组内保持紧凑。

## 先放降压核心

1. 先放 U5、U1，再将每路至少一颗输入电容尽量靠近 2 脚输入和 4 脚地，另外两颗顺着输入铜排开。输入正极与输入地的高频回路同时要短，而不仅是电容中心靠近芯片。
2. 本图保持芯片与现状相同的 0 度方向：3 脚开关输出在左侧，电感安排在左下附近，输入电容在左上。每组都可整体旋转，最终方向由电源进入位置和接口位置决定。电感 1 脚接开关，2 脚接输出；不要按原理图左右方向猜封装编号。
3. R1、C6 或 R6、C14 为自举串联电阻与电容，形成 5 脚到 3 脚之间的短回路。图中的橙色区域提示开关节点应小而集中，避免铺成大片并伸入反馈区。
4. C11 或 C16 靠近 7 脚内部供电并短回流到地。这两颗接内部供电，不是电池输入或 5V 输出。
5. R2、R3、C7 或 R11、R12、C15 安排在 8 脚反馈旁，远离电感和开关铜。从输出电容处单独引回反馈取样。220pF 电容跨在反馈上臂电阻两端，不接地。
6. 输出电容靠近电感输出与功率地，后面再通往每路的过压保护。1 脚模拟地和 4 脚功率地使用同一地网，按厂商要求短而宽连接；不要切出浮动的模拟地岛。

## 再放 USB 小组

1. USB1、USB2 的插口朝板外，具体板边和开口位置仍按 GCT 器件机械图与外壳核对。其后放对应的 U7、U8，不要求两颗控制器排成一排。
2. C104、C106 接控制器的 1 脚输入；C105、C107 接 8 脚输出。前后两种电容不可接到同一个节点。
3. R65、R67 靠近 3 脚限流设定；电阻下端就近接地，避开降压的开关节点和大电流回流。
4. 6 脚配置线 1 接接口 A5，5 脚配置线 2 接接口 B5，二者不能短接。接口焊盘与控制器的引脚次序会导致交叉，最终可使用过孔和另一层绕线；图中虚线仅为连接提示，不保证无交叉单面完成。
5. 接口 A9、B9 两个电源焊盘均接输出。A12、B12 与四个外壳焊盘都保持项目现有的接地关系。小型供电焊盘与热焊盘的实际铜宽和过孔配置另行核算。
6. R66、R68 将 7 脚开漏故障输出上拉到 3.3V。该输出按 HUSB305-02 手册为故障脉冲状态，不应简单当作电源良好静态输出；引到逻辑侧，并避开开关区域。4 脚为未用脚，维持未连接。

## 当前 PCB 的优先调整

当前读取的 PCB 中，U1 与 U5 中心间距约 3.5 mm，但 U1 的 C8～C10 及部分外围仍在另一处；C10 电源焊盘到 U1 输入脚的直线距离约 60.9 mm。建议将 U1 连同其整组外围一起移动成完整小组，或把 U1 移回相应外围附近。对 U5 也先收紧输入电容、开关输出与反馈回路，再接输出保护；数值仅是快照中的焊盘中心距离，用户继续移动后可能变化。

U7 的限流电阻 R65 与控制器仍较分散，应靠近 3 脚。USB 接口位置可优先作为机械约束，之后围绕接口摆控制器、输入/输出电容与限流电阻。

## 依据与核验范围

- [MPS MP2236 手册](https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/EN/sku/MP2236/document_id/4411/)，第 3 页引脚说明、第 17 页 PCB 布局准则、第 20 页 5V 应用电路。要求输入和地连接短而宽、反馈连接短而直接、反馈元件靠近芯片、开关区域远离敏感模拟区域。
- [Hynetek HUSB305 完整手册](https://www.hynetek.com/uploadfiles/site/219/news/2a2293ad-5b62-48ab-b902-a09e7bf50a18.pdf)，引脚说明及第 9 页典型应用；官网当前公开 Rev1.5 文件仅含概览页，具体引脚核对使用官网仍提供的完整 TSOT23-8 文档。
- 四个示意小组按实际封装装配边界的保守包围盒检查无重叠；38 个元件的原理图与 PCB 焊盘网络一致。
- 彩线不是完成走线，过孔图标仅表示就近接地的意图。图中没有完成整板放置、设计规则检查、铜宽、压降、温升或外壳干涉验证。原理图和主 PCB 未修改。
'''
(OUT/'两路5V与USB供电_布局说明.md').write_text(notes,encoding='utf-8')
print(json.dumps(dict(svg=str(OUT/(NAME+'.svg')),parts=38,source_files_unchanged=True),ensure_ascii=False))
