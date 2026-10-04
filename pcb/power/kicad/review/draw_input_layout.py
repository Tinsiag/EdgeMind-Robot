"""Create a placement guide using native KiCad footprint geometry, without saving the board."""
from pathlib import Path
from html import escape
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review' / 'input-layout'
OUT.mkdir(exist_ok=True)
NAME = '电池入口与降压输入_布局示意'
PCB = ROOT / 'ProPrj_power_2026-10-02.kicad_pcb'
SOURCES = [PCB, *sorted(ROOT.glob('*.kicad_sch'))]
HASHES = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
XML = ET.parse(ROOT / 'review' / 'input-layout-current.net.xml').getroot()
COMP = {c.get('ref'): c for c in XML.findall('components/comp')}
NET = {(n.get('ref'), n.get('pin')): net.get('name')
       for net in XML.findall('nets/net') for n in net.findall('node')}
BOARD = pcbnew.LoadBoard(str(PCB))
FP = {f.GetReference(): f for f in BOARD.GetFootprints()}
CURRENT = {}
COL = dict(ink='#172d45', muted='#62788e', edge='#d5e2ed', fab='#5a7087',
           court='#a8b9c8', pad='#e8bb64', power='#d54c5d', gate='#d0861d',
           enable='#8850bd', ref='#287bbb', ground='#23875f')
SVG = ['<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1580" viewBox="0 0 2000 1580">',
       '<defs><style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style></defs>']

# Coordinates are local to three separate enlarged groups, not proposed board coordinates.
PLAN = {
    '入口': dict(CN1=(10,20,0), F1=(18.8,26.89,-90), Q1=(16.31,44.05,0),
                 R51=(12.6,43.225,90), D2=(18.6,46.95,180),
                 D1=(28,47.2,0), C58=(38,44.05,0), C59=(28,51,0), C60=(32,51,0)),
    '开关': dict(Q3=(10,11,180), D3=(7.45,8,0), R53=(7.45,5.8,0),
                 Q4=(14.75,7.9,180), R54=(18.25,8.85,180), C101=(7.495,17.58,-90)),
    '基准': dict(U21=(10,4,0), R52=(6,4,0)),
}
EXPECTED = {
    'CN1': {'1':'GND','2':'BAT_POS'},
    'F1': {'1':'BAT_POS','2':'Net-(Q1-D)'},
    'Q1': {'1':'Net-(D2-A)','2':'Net-(Q1-D)','3':'VBAT_SYS'},
    'D2': {'1':'VBAT_SYS','2':'Net-(D2-A)'},
    'R51': {'1':'Net-(D2-A)','2':'GND'},
    'D1': {'1':'VBAT_SYS','2':'GND'},
    'C58': {'1':'VBAT_SYS','2':'GND'},
    'C59': {'1':'VBAT_SYS','2':'GND'},
    'C60': {'1':'VBAT_SYS','2':'GND'},
    'Q3': {'1':'Net-(D3-A)','2':'VLOGIC_IN','3':'VBAT_SYS'},
    'D3': {'1':'VBAT_SYS','2':'Net-(D3-A)'},
    'R53': {'1':'VBAT_SYS','2':'Net-(D3-A)'},
    'Q4': {'1':'Net-(Q4-B)','2':'GND','3':'Net-(D3-A)'},
    'R54': {'1':'BUCK_ENABLE','2':'Net-(Q4-B)'},
    'C101': {'1':'VLOGIC_IN','2':'GND'},
    'U21': {'1':'VREF_2V495','2':'VREF_2V495','3':'GND'},
    'R52': {'1':'VBAT_SYS','2':'VREF_2V495'},
}
for ref, expected in EXPECTED.items():
    assert FP[ref].GetFPID().GetLibItemName() == COMP[ref].findtext('footprint').split(':',1)[1], ref
    for pin, name in expected.items():
        assert NET[ref, pin] == name, (ref,pin,'schematic')
    for p in FP[ref].Pads():
        if p.GetNumber():
            assert p.GetNetname() == expected[p.GetNumber()], (ref,p.GetNumber(),'pcb')
    f = FP[ref]
    CURRENT[ref] = dict(position=[pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)],
                        angle=f.GetOrientationDegrees(), value=COMP[ref].findtext('value'),
                        footprint=COMP[ref].findtext('footprint'), pins=expected)
assert sum(p.GetNumber()=='1' for p in FP['F1'].Pads()) == 2
assert sum(p.GetNumber()=='2' for p in FP['F1'].Pads()) == 2


def rect(x,y,w,h,fill,stroke='none',radius=0,width=1,dash=''):
    SVG.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" rx="{radius}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-dasharray="{dash}"/>')


def text(s,x,y,size=20,color=None,anchor='start',weight=400):
    SVG.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" fill="{color or COL["ink"]}" '
               f'text-anchor="{anchor}" font-weight="{weight}">{escape(str(s))}</text>')


def line(points,color,width=3,dash=''):
    pts=' '.join(f'{x:.3f},{y:.3f}' for x,y in points)
    SVG.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
               f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}"/>')


def circle(x,y,r,fill='none',stroke='none',width=1):
    SVG.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')


def tag(s,x,y,color,anchor='start'):
    assert s.isascii(),s
    text(s,x,y,17,color,anchor,600)


def arrow(x,y,dx,dy,color):
    length=math.hypot(dx,dy)
    ux,uy=dx/length,dy/length
    line([(x-ux*12-uy*7,y-uy*12+ux*7),(x,y),
          (x-ux*12+uy*7,y-uy*12-ux*7)],color,3)


class Group:
    def __init__(self, name, ox, oy, scale):
        self.name=name
        self.ox,self.oy,self.scale=ox,oy,scale
        self.pins={}
        self.boxes={}
        # Alter only the board object in memory to obtain native transformed geometry.
        for ref,(x,y,angle) in PLAN[name].items():
            f=FP[ref]
            f.SetOrientationDegrees(angle)
            f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
            pins={}
            for p in f.Pads():
                pins.setdefault(p.GetNumber(),[]).append(self.xy(p.GetPosition()))
            self.pins[ref]=pins
            b=f.GetBoundingBox(False,False)
            self.boxes[ref]=[pcbnew.ToMM(b.GetLeft()),pcbnew.ToMM(b.GetTop()),
                             pcbnew.ToMM(b.GetRight()),pcbnew.ToMM(b.GetBottom())]

    def xy(self,v):
        return self.pt(pcbnew.ToMM(v.x),pcbnew.ToMM(v.y))

    def pt(self,x,y):
        return self.ox+x*self.scale,self.oy+y*self.scale

    def pin(self,ref,pin,index=0):
        return self.pins[ref][str(pin)][index]

    def wire(self, points, kind='power', width=3):
        line([self.pt(*p) for p in points],COL[kind],width)

    def ground(self, ref, pin, endpoint, label=False):
        p=self.pin(ref,pin)
        e=self.pt(*endpoint)
        line([p,e],COL['ground'],3)
        circle(*e,6,'#fff',COL['ground'],2)
        circle(*e,2.2,COL['ground'])
        if label: tag('GND',e[0]+12,e[1]+6,COL['ground'])

    def draw(self):
        for ref in PLAN[self.name]:
            f=FP[ref]
            SVG.append(f'<g id="footprint-{ref}">')
            for layer,color,width,dash in [(pcbnew.F_CrtYd,COL['court'],1.2,'4 3'),
                                           (pcbnew.F_Fab,COL['fab'],1.5,'')]:
                for shape in f.GraphicalItems():
                    if shape.GetLayer()!=layer or not isinstance(shape,pcbnew.PCB_SHAPE): continue
                    kind=shape.GetShape()
                    start,end=self.xy(shape.GetStart()),self.xy(shape.GetEnd())
                    if kind==pcbnew.S_SEGMENT:
                        line([start,end],color,width,dash)
                    elif kind==pcbnew.S_RECT:
                        x1,x2=sorted([start[0],end[0]]); y1,y2=sorted([start[1],end[1]])
                        rect(x1,y1,x2-x1,y2-y1,'none',color,0,width,dash)
                    elif kind==pcbnew.S_CIRCLE:
                        circle(*self.xy(shape.GetCenter()),pcbnew.ToMM(shape.GetRadius())*self.scale,'none',color,width)
                    elif kind==pcbnew.S_ARC:
                        # Native arc start/mid/end define its circumcircle, so render exactly.
                        mid=self.xy(shape.GetArcMid())
                        ax,ay=start; bx,by=mid; cx,cy=end
                        det=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
                        if abs(det)<1e-8: continue
                        a2=ax*ax+ay*ay;b2=bx*bx+by*by;c2=cx*cx+cy*cy
                        ux=(a2*(by-cy)+b2*(cy-ay)+c2*(ay-by))/det
                        uy=(a2*(cx-bx)+b2*(ax-cx)+c2*(bx-ax))/det
                        rad=math.hypot(ax-ux,ay-uy)
                        aa=math.atan2(ay-uy,ax-ux); ba=math.atan2(by-uy,bx-ux); ca=math.atan2(cy-uy,cx-ux)
                        sweep=(ca-aa)%(2*math.pi)
                        if (ba-aa)%(2*math.pi)>sweep: sweep-=2*math.pi
                        line([(ux+rad*math.cos(aa+sweep*i/32),uy+rad*math.sin(aa+sweep*i/32))
                              for i in range(33)],color,width,dash)
            for p in f.Pads():
                x,y=self.xy(p.GetPosition()); z=p.GetSize()
                w,h=pcbnew.ToMM(z.x)*self.scale,pcbnew.ToMM(z.y)*self.scale
                orientation=-p.GetOrientationDegrees()
                color=COL['pad']
                SVG.append(f'<g transform="translate({x:.3f},{y:.3f}) rotate({orientation:.3f})">')
                if p.GetShape()==pcbnew.PAD_SHAPE_CIRCLE:
                    circle(0,0,w/2,color,'#b28332',1)
                else:
                    radius=min(w,h)/2 if p.GetShape()==pcbnew.PAD_SHAPE_OVAL else min(w,h)*.18
                    rect(-w/2,-h/2,w,h,color,'#b28332',radius,1)
                drill=p.GetDrillSize(); dw,dh=pcbnew.ToMM(drill.x)*self.scale,pcbnew.ToMM(drill.y)*self.scale
                if dw and dh:
                    rect(-dw/2,-dh/2,dw,dh,'#fff','#a79368',min(dw,dh)/2,.8)
                SVG.append('</g>')
                if p.GetNumber(): text(p.GetNumber(),x,y+4.5,14,'#4f3814','middle',700)
            SVG.append('</g>')

    def label(self,ref,x,y,leader=None,size=20,value=True):
        value_text=COMP[ref].findtext('value')
        if ref=='CN1': value_text='XT60PW-M'
        text(ref,x,y,size,weight=700)
        if value: text(value_text,x,y+26,17,COL['muted'])
        if leader: line([(x+35,y-7),self.pt(*leader)],COL['muted'],1.2)


rect(0,0,2000,1580,'#f3f7fb')
text('电池入口保护 · 母线基准 · 降压输入开关',55,64,38,weight=700)
text('顶层俯视；使用项目原理图的 17 个元件与当前封装。各小组分别放大，彩线为连接提示，最终走线与铜宽另行设计。',55,111,22,COL['muted'])

rect(50,150,900,1150,'#fff',COL['edge'],18,2)
text('① 电池入口：按大电流路径排成一组',78,195,27,weight=700)
A=Group('入口',80,235,17.5)
rect(*A.pt(8,39),38*17.5,17.5*17,'#edf7f1','#d3e9dc',14)
# Input connector and the four real fuse-holder holes.
A.wire([(17.2,20),(18.8,20),(18.8,26.89)],width=5)
A.wire([(15.4,26.89),(18.8,26.89)],width=5)
A.wire([(15.4,36.81),(18.8,36.81),(18.85,44.05)],width=5)
A.wire([(21.39,44.05),(38,44.05)],width=5)
A.wire([(25.85,44.05),(25.85,47.2)],width=4)
A.wire([(27.05,44.05),(27.05,51)],width=3)
A.wire([(34,44.05),(34,51),(31.05,51)],width=3)
A.wire([(12.6,44.05),(16.31,44.05),(16.31,46.95),(16.95,46.95)],'gate')
A.wire([(21.39,44.05),(21.39,46.95),(20.25,46.95)],'power',3)
A.ground('CN1',1,(6,20))
tag('GND',*A.pt(4.5,20.4),COL['ground'],'end')
A.ground('R51',2,(10.3,42.4))
A.ground('D1',2,(32.0,47.2))
A.ground('C59',2,(28.95,53.2))
A.ground('C60',2,(32.95,53.2))
A.ground('C58',2,(44.7,44.05))
A.draw()
text('CN1',*A.pt(7.1,10),25,weight=700)
text('XT60PW-M',*A.pt(7.1,12),18,COL['muted'])
text('插接方向 / 板边',*A.pt(13.6,1),18,COL['power'],'middle')
line([A.pt(13.6,1.6),A.pt(13.6,3.0)],COL['power'],3)
arrow(*A.pt(13.6,3.0),0,1,COL['power'])
text('F1',*A.pt(17.1,32.4),25,anchor='middle',weight=700)
A.label('F1',100,735,(14.0,29.0))
text('同端两孔一起接入',100,796,18,COL['muted'])
text('保留拔插空间',100,824,18,COL['muted'])
A.label('Q1',100,961,(14.0,41.6))
A.label('R51',100,1035,(12.6,43.225))
A.label('D2',100,1110,(18.6,46.95))
text('C58',*A.pt(40.5,42.6),23,anchor='middle',weight=700)
text('470µF / 35V',*A.pt(40.5,46.2),17,COL['muted'],'middle')
text('D1',*A.pt(28,45.5),17,anchor='middle',weight=700)
text('SMBJ15CA',*A.pt(35,49.7),17,COL['muted'],'middle')
text('C59',*A.pt(28,54.6),19,anchor='middle',weight=700)
text('10µF',*A.pt(28,55.9),16,COL['muted'],'middle')
text('C60',*A.pt(32,54.6),19,anchor='middle',weight=700)
text('100nF',*A.pt(32,55.9),16,COL['muted'],'middle')
tag('VBAT_SYS',*A.pt(35.0,37.4),COL['power'])
text('母线向右分配',*A.pt(35,35.7),19,COL['power'])
A.wire([(38,44.05),(38,38.3)],width=3)
tag('GND',*A.pt(43,54.5),COL['ground'],'middle')
text('同一连续地平面',*A.pt(43,55.9),16,COL['ground'],'middle')

rect(530,278,382,426,'#f6f9fc',COL['edge'],12)
for i,(head,rows) in enumerate([
    ('接头靠板边',["线缆从板外进入。","插拔与外壳空间留出来。"]),
    ('保险串在正极入口',["F1 是现有 MINI 底座。","两孔一端，另一两孔一端。"]),
    ('防反接管按焊盘编号接',["Q1：2 脚漏极进，3 脚源极出。","D2 与 R51 靠近 1 脚栅极。"]),
    ('钳位和滤波在保护后',["D1、C59、C60 靠近输出。","C58 留在母线分配点附近。"]),
]):
    y=314+i*98
    text(head,550,y,22,weight=700)
    for j,row in enumerate(rows): text(row,550,y+29+j*26,18,COL['muted'])
text('D1 与电容均并联到电源和地；TVS 回路短而宽。电机支路从保护后的母线另行分出。',78,1251,19)
text('虚线为原封装装配边界；散热空间与操作空间还需额外预留。',78,1278,18,COL['muted'])

rect(980,150,970,740,'#fff',COL['edge'],18,2)
text('② 降压输入：Q3 与栅极驱动收成一组',1008,195,27,weight=700)
text('保持现有 Q3 朝向；将 D3、R53、Q4、R54 移到栅极旁。',1008,233,20,COL['muted'])
B=Group('开关',1050,266,21)
rect(*B.pt(0,3),22*21,23*21,'#edf7f1','#d3e9dc',14)
B.wire([(1,11),(4.92,11)],width=5)
B.wire([(3.6,11),(3.6,5.8),(6.625,5.8)],width=3)
B.wire([(3.6,8),(5.8,8)],width=3)
B.wire([(10,11),(10.5,11),(10.5,5.8),(8.275,5.8)],'gate')
B.wire([(9.1,8),(10.5,8),(10.5,7.9),(13.8125,7.9)],'gate')
B.wire([(15.6875,8.85),(17.425,8.85)],'enable')
B.wire([(19.075,8.85),(22,8.85),(22,4.4)],'enable')
B.wire([(7.46,11),(7.46,17.58),(23,17.58)],width=5)
B.ground('Q4',2,(17.5,6.95))
B.ground('C101',2,(7.495,24.7),True)
B.draw()
tag('VBAT_SYS',*B.pt(0.5,10.0),COL['power'])
tag('BUCK_ENABLE',*B.pt(22,3.8),COL['enable'],'end')
text('由 U22 控制',*B.pt(22,2.4),16,COL['enable'],'end')
tag('GND',*B.pt(17.5,5.8),COL['ground'])
tag('VLOGIC_IN',*B.pt(23,16.6),COL['power'],'end')
text('至三路降压输入',*B.pt(23,19.1),19,COL['power'],'end')
arrow(*B.pt(23,17.58),1,0,COL['power'])
text('R53  10k',*B.pt(7.45,3.9),19,anchor='middle',weight=700)
text('D3',*B.pt(7.45,6.9),16,anchor='middle',weight=700)
text('Q3',*B.pt(7.46,13.0),23,anchor='middle',weight=700)
text('IRF4905',*B.pt(7.46,14.3),17,COL['muted'],'middle')
text('Q4',*B.pt(14.75,10.1),19,anchor='middle',weight=700)
text('MMBT3904',*B.pt(14.75,11.4),16,COL['muted'],'middle')
text('R54',*B.pt(19.1,10.7),19,anchor='middle',weight=700)
text('4.7k',*B.pt(19.1,12.0),16,COL['muted'],'middle')
text('C101',*B.pt(7.495,19.9),23,anchor='middle',weight=700)
text('100µF / 25V',*B.pt(7.495,21.2),17,COL['muted'],'middle')
for i,(head,rows) in enumerate([
    ('Q3 的电流方向与 Q1 相反',["3 脚源极进，2 脚漏极出。","1 脚是栅极，连驱动小组。"]),
    ('D3 与 R53 跨源极和栅极',["D3（BZT52C12）1 脚接源极。","2 脚接栅极，R53 拉回源极。"]),
    ('Q4 与 R54 靠栅极侧',["Q4 的 3 脚集电极拉栅极。","R54 贴近 Q4 的 1 脚基极。"]),
    ('C101 放在开关输出侧',["正极接 Q3 的 2 脚漏极。","仍需保留各降压的输入电容。"]),
]):
    y=298+i*108
    text(head,1592,y,21,weight=700)
    for j,row in enumerate(rows): text(row,1592,y+30+j*27,18,COL['muted'])
text('Q3 下方还需留散热器空间；若装散热器，可把 C101 整体移向左侧或降压输入侧。',1008,831,20)
text('本图校验本组封装装配边界无重叠；并未检查其与整板其他元件、走线及机壳的冲突。',1008,862,18,COL['muted'])

rect(980,910,970,390,'#fff',COL['edge'],18,2)
text('③ 共享基准：U21、R52 留在比较器附近',1008,955,27,weight=700)
text('基准小电流单独取电；回流走同一地平面，避开电机与开关电流的主通道。',1008,992,20,COL['muted'])
C=Group('基准',1070,1000,35)
rect(1090,1031,488,204,'#edf7f1','#d3e9dc',14)
C.wire([(5.175,4),(4.0,4)],width=3)
C.wire([(6.825,4),(8.0,4),(8.0,3.05),(9.0625,3.05)],'ref')
C.wire([(8.0,4),(8.0,4.95),(9.0625,4.95)],'ref')
C.wire([(8.0,4),(8.0,2.1),(15.5,2.1)],'ref')
C.ground('U21',3,(12.5,4),True)
C.draw()
tag('VBAT_SYS',*C.pt(4.0,3.0),COL['power'],'end')
text('R52  2.2k',*C.pt(6,5.8),19,anchor='middle',weight=700)
text('U21  TL431BIDBZR',*C.pt(10,6.7),19,anchor='middle',weight=700)
text('1、2 脚在器件旁短接',*C.pt(4.8,0.8),18,COL['ref'])
tag('VREF_2V495',*C.pt(15.5,1.6),COL['ref'],'end')
for i,ref in enumerate(['U22','U23']):
    x,y=1680,1040+i*100
    rect(x,y,210,78,'#f5f9fd',COL['edge'],10)
    text(ref+'  LM393B',x+18,y+29,20,weight=700)
    text('2、5 脚参考输入',x+18,y+57,17,COL['ref'])
    line([C.pt(15.5,2.1),(1633,C.pt(15.5,2.1)[1]),(1633,y+40),(x,y+40)],COL['ref'],3,'7 5')
text('基准输出不要直接增加任意电容；是否加电容应核对 TL431 的稳定区间。',1008,1268,19)

rect(50,1335,1900,194,'#fff',COL['edge'],18,2)
text('摆放顺序：接头 → 保险 → 防反接 → 钳位与母线滤波 → 分支开关 → 各降压输入',78,1378,26,weight=700)
for x,label,kind in [(80,'功率连接','power'),(380,'栅极连接','gate'),(680,'控制输入','enable'),
                      (990,'基准分配','ref'),(1300,'地平面连接','ground')]:
    line([(x,1417),(x+48,1417)],COL[kind],4)
    text(label,x+61,1424,20,COL[kind])
text('两颗 TO-220 的金属片均为 2 脚漏极，不能直接当接地散热片；共用导电散热器时需要电气绝缘。',78,1463,22)
text('彩线表示连接关系，不表示完成布线、固定线宽或固定层。电容正负极、实际器件尺寸与散热空间需在最终 PCB 中复核。',78,1501,20,COL['muted'])
text('根据当前原理图与 PCB 核对 · 仅新增布局参考图 · 各小组可整体平移或旋转',55,1560,19,COL['muted'])
SVG.append('</svg>')
(OUT/(NAME+'.svg')).write_text('\n'.join(SVG),encoding='utf-8')

# Conservative independent bounding-box check on the actual transformed native courtyards.
COURTS={}
for group in PLAN:
    rows={}
    for ref in PLAN[group]:
        shapes=[s for s in FP[ref].GraphicalItems() if s.GetLayer()==pcbnew.F_CrtYd]
        pts=[]
        for s in shapes:
            b=s.GetBoundingBox()
            pts.extend([(pcbnew.ToMM(b.GetLeft()),pcbnew.ToMM(b.GetTop())),
                        (pcbnew.ToMM(b.GetRight()),pcbnew.ToMM(b.GetBottom()))])
        rows[ref]=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]
    for i,a in enumerate(rows):
        for b in list(rows)[i+1:]:
            ax,ay,ar,ab=rows[a];bx,by,br,bb=rows[b]
            assert min(ar,br)<=max(ax,bx) or min(ab,bb)<=max(ay,by), (group,a,b,'courtyard')
    COURTS[group]=rows
for path,old in HASHES.items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==old,(path,'source changed during rendering')

notes='''# 电池入口与降压输入布局说明

本图使用当前原理图中的 17 个元件，封装的焊盘中心、尺寸、编号、装配边界和器件轮廓从当前 KiCad PCB 读取。三组分别放大，是摆放参考，图中彩线仅提示连接关系；没有更改原理图或主 PCB。

## 目前可以保留的摆放

- CN1、F1、Q1 已按入口电流路径纵向排列；保持接头靠板边、保险可拔插。
- D2 与 R51 已靠近 Q1，当前焊盘中心到栅极约为 2.9 mm 和 3.7 mm，可以保持这个小组。
- U21、R52 已在 U22、U23 附近，可继续保持；基准回路不要移到功率管或电机回流旁边。

## 建议移动的元件

- 将 D1、C59、C60 移近 Q1 输出和母线分配处，C58 留在旁边。D1 是并联的双向 TVS，不是串联器件；其电源到地回路尽量短而宽。当前 D1 电源焊盘到 Q1 输出焊盘中心约 10.4 mm，是位置距离，不是已经布好的线长。
- 将 D3、R53、Q4、R54 作为小组移到 Q3 栅极侧。目前 D3、R53、Q4 相关焊盘到栅极约为 10～13 mm。本图把这些元件收紧，并按正确的源极与栅极连接方向放置。
- C101 已在 Q3 输出侧附近，可保持正极朝开关输出的原则；有散热器时让出其机械空间。三路降压芯片自身的输入电容仍应靠近各自的电源与地引脚。

## 必须按焊盘编号核对

| 元件 | 正确连接 |
|---|---|
| CN1 | 2 脚为电池正极，1 脚为地；插头极性仍须核对实物 |
| F1 | 四个孔是 1、1、2、2，两孔共用同一端；1 端接电池正极，2 端接防反接管入口 |
| Q1 | IRF4905 的 1 脚栅极、2 脚漏极、3 脚源极；防反接电流从 2 脚进入、3 脚出去 |
| D2、R51 | D2 阴极 1 脚接 Q1 源极，阳极 2 脚接栅极；R51 把栅极拉到地 |
| Q3 | 同样是 1 脚栅极、2 脚漏极、3 脚源极；开关电流从 3 脚进入、2 脚出去 |
| D3、R53 | D3 阴极 1 脚接 Q3 源极，阳极 2 脚接栅极；R53 在源极和栅极之间 |
| Q4、R54 | Q4 的 3 脚集电极接 Q3 栅极，2 脚发射极接地，1 脚基极接 R54；R54 另一端接比较器控制输出 |
| C101 | 正极 1 脚接 Q3 的 2 脚输出，负极 2 脚接地 |
| U21、R52 | TL431BIDBZR 的 1 脚阴极与 2 脚参考端短接，3 脚阳极接地；R52 从保护后的电池母线为其供电 |

## 布线、地与散热

1. 大电流路径用宽铜或铜皮，避免接头、保险、功率管之间的细长颈部；具体宽度需结合设计电流、铜厚、温升和散热计算。图中的线宽不是铜宽要求。
2. 地保持同一个连续地平面。TVS、电解电容与电机的高电流回路安排在功率区；基准、比较分压下端和比较器的回流在安静区域，不与大电流共用狭窄铜颈。
3. 基准供电从保护后的母线独立引出；避免在电机电流路径的末端取样或回流。基准输出分到两颗比较器的参考输入，避开降压开关节点与电机输出线。
4. 本项目使用 TL431 的 DBZ 封装。TI 手册中的 TL432-DBZ 布局示例，1、2 脚功能与 TL431 不同，不能直接照搬编号。给阴极增加电容前需核对手册稳定性曲线。
5. 两颗 IRF4905 金属片均连接漏极，实际连接的是不同电气节点。金属散热器不能直接接地，两颗共用导电散热器时须使用绝缘垫与绝缘套。封装装配边界没有覆盖所有可选散热器及插拔工具空间。

## 核验范围

已核对上述 17 个元件的原理图引脚网络与 PCB 焊盘网络一致；示意摆放的各小组在保守的装配边界包围盒检查中无重叠。图中坐标仅用于三幅独立小组的绘图，不是要直接写入整板的放置坐标，尚未检查示意小组与整板其余元件、现有铜和机壳的冲突。

主 PCB 的只读 DRC 仍有既存违规和未连接项，本图不能替代整板 DRC。R53 与 Q4 的装配边界包围盒看似相交，但 Q4 的真实边界有凹口，此次原生 DRC 没有报告二者装配边界重叠，不能据包围盒误判碰撞。

参考手册：[TI TL431/TL432，5 引脚说明、9.4 供电与 9.5 布局](https://www.ti.com/lit/ds/symlink/tl431.pdf)，[Infineon IRF4905](https://www.infineon.com/assets/row/public/documents/24/49/infineon-irf4905-datasheet-en.pdf)。封装几何取自项目的 KiCad 原生文件，具体推荐摆放属于本次工程分析。
'''
(OUT/'电池入口与降压输入_布局说明.md').write_text(notes,encoding='utf-8')
audit=dict(元件数=len(EXPECTED), 元件= CURRENT, 原理图与PCB焊盘网络核对='通过',
           分组示意坐标=PLAN, 分组装配边界包围盒=COURTS, 本组装配边界包围盒重叠=False,
           原文件SHA256=HASHES, 原文件修改=False,
           说明='独立小组的顶层示意，未完成整板放置、走线、散热或电流承载验证')
(OUT/'绘图核验.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(svg=str(OUT/(NAME+'.svg')),parts=len(EXPECTED),source_files_unchanged=True),ensure_ascii=False))
