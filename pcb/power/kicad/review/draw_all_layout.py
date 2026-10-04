"""Read-only PCB placement atlas: native footprints, verified pin links, complete coverage."""
from pathlib import Path
from html import escape
import ast, hashlib, json, math, shutil, csv
import xml.etree.ElementTree as ET
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/all-layout'; OUT.mkdir(exist_ok=True)
PCB=ROOT/'ProPrj_power_2026-10-02.kicad_pcb'
SOURCES=[PCB,*sorted(ROOT.glob('*.kicad_sch'))]
HASHES={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
AUDIT=json.loads((ROOT/'review/all-layout-current.json').read_text(encoding='utf-8'))
XML=ET.parse(ROOT/'review/all-layout-current.net.xml').getroot()
COMP={c.get('ref'):c for c in XML.findall('components/comp')}
NET={(n.get('ref'),n.get('pin')):net.get('name') for net in XML.findall('nets/net') for n in net.findall('node')}
BOARD=pcbnew.LoadBoard(str(PCB)); FP={f.GetReference():f for f in BOARD.GetFootprints()}
COL=dict(ink='#172d45',muted='#62788e',edge='#d5e2ed',fab='#5a7087',court='#a8b9c8',pad='#e8bb64',power='#d54c5d',gate='#d0861d',enable='#8850bd',ref='#287bbb',ground='#23875f')
SVG=[]; PLAN={}; INFO={}; PAGES=[]; COVER={}; CHECKS=[]; LINKS=[]
helper=(ROOT/'review/draw_input_layout.py').read_text(encoding='utf-8')
defs=[ast.get_source_segment(helper,n) for n in ast.parse(helper).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'rect','text','line','circle','tag','arrow','Group'}]
exec(compile('\n\n'.join(defs).replace("14,'#4f3814'","12 if len(p.GetNumber())>2 else 14,'#4f3814'"),'native-svg-helper','exec'),globals())

for r,f in FP.items():
 assert r in COMP
 assert f.GetFPID().GetLibItemName()==COMP[r].findtext('footprint').split(':',1)[1],r
 for p in f.Pads():
  if p.GetNumber(): assert p.GetNetname()==NET[r,p.GetNumber()],(r,p.GetNumber())

def start(title,subtitle,w=2300,h=1550):
 global SVG,W,H
 W,H=w,h
 SVG=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">','<defs><style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style></defs>']
 rect(0,0,w,h,'#f2f6fa');text(title,55,66,38,weight=700);text(subtitle,55,108,21,COL['muted'])

def finish(name,refs,summary):
 text('顶层俯视 · 金色为真实焊盘，虚线为封装占位；彩线只示意关键连接，交叉不表示相连。各局部图分别缩放。',55,H-55,20,COL['muted'])
 text('2026-10-04 · 原理图与 PCB 源文件未修改 · 完整物料、局部坐标、核验及手册链接见图册索引',55,H-25,18,COL['muted'])
 (OUT/(name+'.svg')).write_text('\n'.join(SVG+['</svg>']),encoding='utf-8')
 PAGES.append(dict(name=name,refs=sorted(refs),summary=summary))
 for r in refs:COVER.setdefault(r,[]).append(name)

def group(name,plan,title,notes,edges=(),grounds=True):
 PLAN[name]=plan;INFO[name]=dict(title=title,notes=notes,edges=edges,grounds=grounds)

def box_for(f):
 bs=[s.GetBoundingBox() for s in f.GraphicalItems() if isinstance(s,pcbnew.PCB_SHAPE) and s.GetLayer()==pcbnew.F_CrtYd]
 if not bs:bs=[f.GetBoundingBox(False,False)]
 return [min(pcbnew.ToMM(b.GetLeft()) for b in bs),min(pcbnew.ToMM(b.GetTop()) for b in bs),max(pcbnew.ToMM(b.GetRight()) for b in bs),max(pcbnew.ToMM(b.GetBottom()) for b in bs)]

def overlap(a,b,gap=0):
 return min(a[2],b[2])-max(a[0],b[0])>gap and min(a[3],b[3])-max(a[1],b[1])>gap

def draw_card(name,x,y,w,h):
 d=INFO[name];rect(x,y,w,h,'#fff',COL['edge'],15,2)
 text(d['title'],x+25,y+40,25,weight=700)
 # Transform once to measure native courtyards, then fit into a reserved diagram rectangle.
 G=Group(name,0,0,1);bs={r:box_for(FP[r]) for r in PLAN[name]}
 collisions=[]
 for i,a in enumerate(bs):
  for b in list(bs)[i+1:]:
   if overlap(bs[a],bs[b],0.01):collisions.append([a,b])
 CHECKS.append(dict(group=name,parts=len(bs),courtyard_box_overlaps=collisions))
 xmin=min(b[0] for b in bs.values())-2.5; xmax=max(b[2] for b in bs.values())+2.5
 ymin=min(b[1] for b in bs.values())-2.5; ymax=max(b[3] for b in bs.values())+2.5
 note_height=32*len(d['notes'])+45
 dh=h-95-note_height; dw=w-85
 sc=min(dw/(xmax-xmin),dh/(ymax-ymin),39)
 ox=x+42+(dw-(xmax-xmin)*sc)/2-xmin*sc
 oy=y+70+(dh-(ymax-ymin)*sc)/2-ymin*sc
 G=Group(name,ox,oy,sc)
 # Reference plane is a continuous plane; the tinted box is just explanatory.
 rect(x+22,y+58,w-44,dh+15,'#f7fafc',radius=8)
 for edge in d['edges']:
  a,pa,b,pb,*extras=edge;kind=extras[0] if extras else 'ref'
  assert NET[a,str(pa)]==NET[b,str(pb)],(name,edge,NET[a,str(pa)],NET[b,str(pb)])
  pts=[G.pin(a,pa)]
  if len(extras)>1:pts += [G.pt(*p) for p in extras[1]]
  pts += [G.pin(b,pb)]
  line(pts,COL[kind],4 if kind=='power' else 2.5,'5 4' if kind=='ref' else '')
  LINKS.append(dict(group=name,a=[a,str(pa)],b=[b,str(pb)],net=NET[a,str(pa)]))
 if d['grounds']:
  for r in PLAN[name]:
   for p in FP[r].Pads():
    if p.GetNumber() and p.GetNetname()=='GND':
     px,py=G.xy(p.GetPosition());circle(px,py,7,'none',COL['ground'],2)
 G.draw()
 # Labels avoid every courtyard and previously placed labels. Leaders disambiguate dense groups.
 occupied=[[G.pt(b[0],b[1])[0]-3,G.pt(b[0],b[1])[1]-3,G.pt(b[2],b[3])[0]+3,G.pt(b[2],b[3])[1]+3] for b in bs.values()]
 for r in sorted(PLAN[name],key=lambda r:-(bs[r][2]-bs[r][0])*(bs[r][3]-bs[r][1])):
  b=bs[r]; l,t=G.pt(b[0],b[1]); rr,bb=G.pt(b[2],b[3]);cx,cy=(l+rr)/2,(t+bb)/2
  size=21; tw=len(r)*size*.63+12;th=25
  candidates=[]
  # Large body can carry its own reference at center without touching pins.
  if r!='U13' and r.startswith(('U','Q','L')) and (rr-l)>85 and (bb-t)>65:
   candidates.append((cx,cy,True))
  for off in [14,37,60,86]:
   candidates += [(cx,t-off,False),(cx,bb+off+12,False),(l-off-tw/2,cy,False),(rr+off+tw/2,cy,False)]
  chosen=None
  for tx,ty,inside in candidates:
   test=[tx-tw/2,ty-th*.75,tx+tw/2,ty+7]
   if not(x+6<test[0] and test[2]<x+w-6 and y+58<test[1] and test[3]<y+58+dh+15):continue
   if inside or not any(overlap(test,o) for o in occupied):chosen=(tx,ty,inside,test);break
  if chosen is None:
   tx,ty,inside=candidates[-1];test=[tx-tw/2,ty-19,tx+tw/2,ty+7];chosen=(tx,ty,False,test)
  tx,ty,inside,test=chosen
  if not inside:line([(tx,ty-7),(cx,cy)],'#879bad',1)
  rect(test[0],test[1],tw,th,'#ffffff',radius=3)
  text(r,tx,ty,21,anchor='middle',weight=700);occupied.append(test)
 # Scale is local, not a claim about the eventual board outline.
 sy=y+58+dh+8;sx=x+35
 line([(sx,sy),(sx+5*sc,sy)],COL['ink'],2);text('5 mm',sx+5*sc+10,sy+6,15,COL['muted'])
 for i,n in enumerate(d['notes']):text(n,x+25,y+h-note_height+29+i*32,20,COL['ink'])
 return set(PLAN[name])

def E(a,p,b,q,k='ref',via=None):
 return (a,p,b,q,k,via) if via is not None else (a,p,b,q,k)

# 03: fixed 3.3 V converter and the manually selected alternate input.
group('aux_buck',dict(U3=(10,10,0),C108=(10,13.7,0),C109=(14,7.8,90),L3=(19,13.7,0),C110=(19,20,0),C111=(23,20,0)),
 '① 独立 3.3V 降压核心',[
 'C108 紧靠 U3 的 3、4 脚；底层保留连续地铜。',
 'C109 靠 5、6 脚，L3 靠 5 脚；开关铜保持小而宽。',
 'C110/C111 位于电感输出侧；1 脚从输出电容处取样。',
 '固定输出芯片不增加分压电阻；反馈线绕开电感。'],[
 E('C108',1,'U3',3,'power'),E('U3',5,'L3',1,'gate',[(13,10),(13,13.7)]),E('C109',1,'U3',5,'gate'),E('C109',2,'U3',6,'gate'),E('L3',2,'C110',1,'power',[(24.5,13.7),(24.5,18.5),(18.05,18.5)]),E('C110',1,'C111',1,'power',[(18.05,18.5),(22.05,18.5)]),E('C110',1,'U3',1,'ref',[(5,20),(5,6),(8.8625,6)])])
group('aux_select',dict(J9=(2,3,90),JP1=(10,7,90),J14=(25,8,0),FB1=(12,17,0),C112=(18,17,0),C113=(18,20.5,0)),
 '② 先保护，再选电源，再分配',[
 '降压输出先经过图 11 的 Q12 保护，才接 JP1 的 1 脚。',
 'JP1 默认短接 1—2；选择外部输入时改接 2—3。',
 'J9 靠近 JP1，跳帽上方留出手指操作空间。',
 'FB1 后紧接 C112/C113，再分到四个传感器接口。'],[
 E('J9',1,'JP1',3,'power'),E('JP1',2,'J14',1,'power'),E('JP1',2,'FB1',1,'power'),E('FB1',2,'C112',1,'power'),E('C112',1,'C113',1,'power')])
portplan={};portedges=[]
for j,c,x in [('J10','C114',4),('J11','C115',16),('J12','C116',28),('J13','C117',40)]:
 portplan[j]=(x,5,0);portplan[c]=(x+1,11,0);portedges.append(E(j,1,c,1,'power'))
group('aux_ports',portplan,'③ 传感器连接器排在安静侧板边',[
 'J10 为惯性传感器；J11/J12/J13 为三路测距电源。',
 '每颗 100nF 紧靠对应接口；电源与回流相邻引出。',
 '这一页提供电源，图中接口没有传感器通信信号。'],portedges)

# 04 plus the physically shared PWM gate U11 from sheets 05/06.
group('safety',dict(J15=(0,4,0),R69=(9.5,10,90),R70=(8,13.5,90),R72=(8,17,90),U10=(15,14,0),C118=(20.6,10.2,0),U12=(29,14,0),C119=(34.6,10.2,0),R71=(23,15,0),R73=(23,20,0),U13=(13,25,90),C120=(18,23.7,0)),
 '① 急停、上电复位与故障锁存',[
 'J15 靠板边，U10 → U12 靠近；复位输入走短线。',
 'C118/C119 分别贴 14 脚，C120 贴 U13 的 2 脚。',
 'R69/R70/R72 放到接收端附近；R71 靠 U12 的 3 脚。',
 'J15 断开触发禁止；外部线束从安静侧进入。'],[
 E('J15',2,'R69',1,'enable'),E('R69',1,'U10',1,'enable'),E('R70',1,'U10',2,'enable'),E('R72',2,'U10',5,'enable'),E('U10',11,'U12',1,'enable'),E('R71',1,'U12',3,'enable'),E('U12',5,'R73',1,'enable'),E('U10',14,'C118',1,'power'),E('U12',14,'C119',1,'power'),E('U13',2,'C120',1,'power'),E('U13',1,'U10',4,'enable',[(10,25),(10,14)])])
group('pwm_gate',dict(U11=(10,10,0),C127=(15.6,6.2,0)),
 '② U11 只放一颗，位于两块驱动模块之间',[
 'U11 的四个与门共同放行左右电机的四路控制。',
 'C127 是这颗芯片的 100nF 去耦，靠 14 脚。',
 '左侧 3、6 脚去 U2；右侧 8、11 脚去 U4。',
 'U12 的 5 脚同时控制 U11 与图 09 的 Q2 开关。',
 '原理图跨两页显示同一 U11，不能在 PCB 上复制。'],[E('U11',14,'C127',1,'power')])

# Motor page objects use each existing, asymmetric module footprint unchanged.
MOTOR=[dict(k='L',u='U2',j='J3',bulk='C122',cer='C123',uim='U25',sh='R84',cb='C124',rf='R85',cf='C125',rv='RV1',rvf='R86',rvd='R87',rvc='C126',pd1='R88',pd2='R89',ec='C130',er1='R90',ep1='R91',er2='R92',ep2='R93',ec1='C128',ec2='C129'),dict(k='R',u='U4',j='J4',bulk='C131',cer='C132',uim='U26',sh='R94',cb='C133',rf='R95',cf='C134',rv='RV2',rvf='R96',rvd='R97',rvc='C135',pd1='R98',pd2='R99',ec='C138',er1='R100',ep1='R101',er2='R102',ep2='R103',ec1='C136',ec2='C137')]
for m in MOTOR:
 u,j=m['u'],m['j'];k=m['k'];row=23.0005 if k=='L' else 23.1275
 group(k+'_module',{u:(12,10,0),j:(-2,10,-90),m['bulk']:(3,33,0),m['cer']:(8.3,25,0),m['pd1']:(39.5,20.16,0),m['pd2']:(39.5,17.62,0),m['ec']:(4.5,12.5,0)},
  '① 模块排母、储能电容和电机接口',[
  f'{u} 左排由上到下 1—7，右排由上到下 8—14。',
  f'两排中心距 {row} mm；沿用原封装，插接仍需实物核对。',
  f'{m["bulk"]}/{m["cer"]} 靠电源端，{j} 靠模块输出与板边。',
  '模块投影内不塞高元件；右侧两个下拉靠控制引脚。'],[
  E(u,1,j,1,'power'),E(u,2,j,6,'power'),E(m['cer'],1,u,6,'power'),E(m['bulk'],1,m['cer'],1,'power'),E(u,6,u,9,'power',[(9,31),(39,31),(39,12.54)]),E(m['pd1'],1,u,12,'enable'),E(m['pd2'],1,u,11,'enable'),E(m['ec'],1,j,2,'power')])
 group(k+'_sense',{m['sh']:(10,14,0),m['uim']:(10,9,0),m['cb']:(14.5,8,0),m['rf']:(5,8,180),m['cf']:(1,8,180)},
  '② 高侧采样：电阻在主功率通路，检测在旁边',[
  f'{m["sh"]} 串在模块供电前；1 脚进，2 脚出。',
  '两根蓝线从电阻焊盘靠电阻体的一侧单独引出。',
  f'{m["uim"]} 3 脚接上游，4 脚接下游；不得共用大电流线段。',
  f'{m["cb"]} 靠 5 脚；{m["rf"]}/{m["cf"]} 位于 1 脚输出侧。'],[
  E(m['sh'],1,m['uim'],3,'ref',[(7.8,12),(8.8625,12)]),E(m['sh'],2,m['uim'],4,'ref',[(12.2,12),(11.1375,12)]),E(m['cb'],1,m['uim'],5,'power'),E(m['uim'],1,m['rf'],1,'ref'),E(m['rf'],2,m['cf'],1,'ref')])
 group(k+'_ref',{m['rv']:(10,6,0),m['rvf']:(7.46,12,-90),m['rvc']:(7.46,16,-90),m['rvd']:(11.5,16,-90)},
  '③ 模块限流参考，放在模块控制侧',[
  f'{m["rv"]} 螺丝顶部留调节空间，避开电解电容。',
  f'{m["rvf"]}/{m["rvc"]}/{m["rvd"]} 靠模块的 5、10 脚。',
  '参考与其地一起靠安静侧走，不跟随电机输出线。',
  '先实测模块内部采样阻值，再调电位器定限流。'],[
  E(m['rv'],2,m['rvf'],1,'ref'),E(m['rvf'],2,m['rvc'],1,'ref'),E(m['rvd'],1,m['rvc'],1,'ref')])
 group(k+'_encoder',{m['er1']:(5,7,0),m['ep1']:(10,3,-90),m['ec1']:(10,10,-90),m['er2']:(18,7,0),m['ep2']:(23,3,-90),m['ec2']:(23,10,-90)},
  '④ 编码器滤波，靠控制排针一侧',[
  f'{m["er1"]}/{m["er2"]} 串在接收端；电容接在串阻之后。',
  '上拉、电容与控制接口放成小组；输出线尽量短。',
  '两路编码器信号从电机接口离开后绕开功率输出。',
  '电机与编码器共用插座，入口处分流后各走各的区域。'],[
  E(m['er1'],2,m['ep1'],2,'ref'),E(m['er1'],2,m['ec1'],1,'ref'),E(m['er2'],2,m['ep2'],2,'ref'),E(m['er2'],2,m['ec2'],1,'ref')])

# 07: physically spread the shared circuit into switch, comparator, two local dump power loops.
group('motor_switch',dict(Q2=(10,11,180),D4=(7.45,8,0),R74=(7.45,5.8,0),Q5=(14.75,7.9,180),R75=(18.5,8.85,180),TP1=(3,17,0)),
 '① 电机总开关靠近电池分支',[
 'Q2 的 3 脚进、2 脚出；输出再分到 R84/R94。',
 'D4/R74 靠栅源，Q5/R75 靠栅极；TP1 留表笔位置。',
 'Q2 的散热片与 Q1/Q3 不可直接金属共连。'],[
 E('Q2',1,'D4',2,'gate'),E('Q2',3,'D4',1,'power'),E('R74',2,'Q2',1,'gate'),E('Q5',3,'Q2',1,'gate'),E('R75',2,'Q5',1,'enable'),E('Q2',2,'TP1',1,'power')])
group('dump_compare',dict(U24=(12,10,0),C121=(17.8,8.1,0),R76=(5,10.635,0),R77=(5,14,0),R79=(5,6.8,0),R80=(20,11.9,180),R81=(20,15.3,0),R83=(24,8.5,90)),
 '② 回生比较器居两路之间，靠安静边界',[
 'C121 靠 8 脚；左右分压和迟滞电阻各靠对应输入。',
 '左右母线分别采样；基准由 U21 沿安静区引入。',
 '比较器输出去功率管栅极，远离输入和取样线。'],[
 E('U24',8,'C121',1,'power'),E('R76',2,'U24',3),E('R77',1,'U24',3),E('R79',1,'U24',3),E('R79',2,'U24',1,'enable'),E('R80',2,'U24',5),E('R81',1,'U24',5),E('R83',1,'U24',5),E('R83',2,'U24',7,'enable',[(24,5),(16,5),(16,9.365)])])
for name,q,j,d,r in [('dumpL','Q6','J16','D5','R78'),('dumpR','Q7','J17','D6','R82')]:
 group(name,{q:(10,13,0),j:(11,3,0),d:(5.8,12,90),r:(7,7,90)},
  f'③ {j}/{q}：每路泄放各靠自己的模块',[
  f'{j} → 外置 3.3Ω 功率电阻 → {q} 的 2 脚 → 地。',
  f'{d} 靠 {q} 的栅源；{r} 靠栅极，上游来自本路母线。',
  '功率管和外部电阻朝板外散热，热区避开比较器。'],[
  E(j,2,q,2,'power'),E(d,1,q,1,'gate'),E(r,2,q,1,'gate'),E(j,1,r,1,'power')])

# 08: each 5 V protection travels with its own buck / USB channel.
for k,u,q,n,d,ra,rb,rp,rg,rdrive,cap in [('protect5L','U27','Q8','Q9','D7','R104','R105','R106','R107','R108','C139'),('protect5R','U28','Q10','Q11','D8','R109','R110','R111','R112','R113','C140')]:
 group(k,{q:(22,7,0),d:(18,12.5,0),rg:(18,15,0),n:(23,15,0),rdrive:(23,19,90),u:(12,24,0),cap:(17.8,22.1,0),ra:(5,21.9,90),rb:(5,26,90),rp:(7,18,0)},
  ('① 逻辑板 5V 过压保护' if k.endswith('L') else '② 计算板 5V 过压保护'),[
  f'{q} 排在降压输出电容和 USB 控制器之间，1—3 脚进、5—8 脚出。',
  f'{d}/{rg}/{n} 靠栅极；{ra}/{rb} 靠 {u} 的 2 脚。',
  f'{cap} 靠 8 脚；电压从功率管前端取样，输入分压走安静侧。',
  '源极、漏极分别铺宽铜；栅极线不要割断主功率铜。',
  '左图输出送 U7，右图输出送 U8；两路输出保持独立。'],[
  E(q,1,q,2,'power'),E(q,2,q,3,'power'),E(q,5,q,6,'power'),E(q,6,q,7,'power'),E(q,7,q,8,'power'),E(q,4,d,2,'gate'),E(q,1,d,1,'power'),E(q,4,rg,2,'gate'),E(q,4,n,3,'gate'),E(rdrive,2,n,1,'enable'),E(u,1,rdrive,1,'enable'),E(rp,2,u,1,'enable'),E(ra,2,u,2),E(rb,1,u,2),E(cap,1,u,8,'power')])
group('protect3',dict(Q12=(22,6,180),R116=(17.5,6,180),Q13=(22,11,180),R117=(22,15,90),U29=(12,21,0),C141=(17.8,19.1,0),R114=(5,19,90),R115=(5,23,90),R118=(7,15,0),R119=(20,25,90),R120=(16,25,0),R121=(19,21.7,0)),
 '① 3.3V 过压保护与电池预警共用 U29',[
 'Q12 位于 U3 输出与 JP1 之间；2 脚进、3 脚出。',
 'R114/R115 靠 U29 的 2 脚；R119/R120 靠 5 脚。',
 'C141 靠 8 脚，Q13/R116/R117 靠 Q12 的栅极。',
 '电池分压从入口受保护母线取样，输出预警去 J18。'],[
 E('Q12',1,'R116',1,'gate'),E('Q12',1,'Q13',3,'gate'),E('Q13',1,'R117',2,'enable'),E('R117',1,'U29',1,'enable'),E('R118',2,'U29',1,'enable'),E('R114',2,'U29',2),E('R115',1,'U29',2),E('R119',2,'U29',5),E('R120',1,'U29',5),E('R121',2,'U29',7,'enable'),E('C141',1,'U29',8,'power')])
group('overcurrent',dict(U30=(12,10,0),C142=(17.8,8.1,0),R122=(7,6,-90),R123=(7,10,-90)),
 '② 双电机过流比较，靠两路检测的汇合处',[
 'R122/R123 靠 U30，形成共享电流比较基准。',
 'C142 贴 8 脚；两路滤波后的电流信号分别进 2、6 脚。',
 '1、7 脚与 U23 的开集电极输出汇合，再到安全逻辑。',
 '只把已放大的电流信号送来，采样电阻留在电机侧。'],[
 E('C142',1,'U30',8,'power'),E('R122',2,'R123',1),E('R123',1,'U30',3),E('R123',1,'U30',5),E('U30',1,'U30',7,'enable')])

# 09: connector pin 1 remains explicitly visible and ADC filtering stays at the receiver.
group('control',dict(J1=(5,5,-90),J2=(5,16,-90),J18=(5,30,-90),R124=(1,23,0),R125=(5,26,90),C143=(0,27,180)),
 '控制与监测接口：集中在安静侧板边',[
 'J1/J2 同侧排齐，但各自针序不同，按图中的 1 脚识别。',
 'J18 靠电流比较与安全逻辑，保留插拔和表笔空间。',
 'R124/R125/C143 靠 J18 的 3 脚；输出采样线短。',
 '左右编码器滤波组分别移到 J1/J2 附近，不经过电感下方。',
 '这些排针没有锁扣；实际线束方向决定最终连接器朝向。'],[
 E('R124',2,'R125',1),E('R125',1,'C143',1),E('C143',1,'J18',3)])

# Page production. Each native footprint is drawn once in the new details.
start('05 · 独立 3.3V 与传感器供电','对应原理图第 03 页 · 主电源、可选外部输入、辅助输出和四个传感器接口')
rs=draw_card('aux_buck',45,145,1055,755)|draw_card('aux_select',1125,145,1130,755)|draw_card('aux_ports',45,925,2210,495)
finish('05_独立3V3与传感器',rs,'降压核心、受保护电源选择与传感器接口分三组。')
start('06 · 急停锁存与双轮控制门','对应原理图第 04 页及跨第 05/06 页的 U11 · 安全输入从安静侧进，控制输出朝电机侧出')
rs=draw_card('safety',45,150,1390,1250)|draw_card('pwm_gate',1460,150,795,1250)
finish('06_急停锁存与控制门',rs,'U11 是一颗共享芯片，和去耦 C127 一起靠近安全逻辑。')
for idx,m in enumerate(MOTOR):
 side='左' if idx==0 else '右'; k=m['k']
 start(f'{7+idx:02d} · {side}轮 AT8236 模块与外围',f'对应原理图第 {5+idx:02d} 页 · 模块实际排母封装；电流检测、限流参考、编码器滤波各自成组',2500,1850)
 rs=draw_card(k+'_module',45,145,1330,855)|draw_card(k+'_sense',1400,145,1055,855)|draw_card(k+'_ref',45,1025,1120,690)|draw_card(k+'_encoder',1190,1025,1265,690)
 finish(f'{7+idx:02d}_{side}轮模块与检测',rs,'模块与功率线靠板边；编码器滤波应移到对应控制排针旁。')
start('09 · 电机总开关与两路回生泄放','对应原理图第 07 页 · 电机供电开关靠入口，两路泄放分别靠各自电机母线',2500,1750)
rs=draw_card('motor_switch',45,145,1155,705)|draw_card('dump_compare',1225,145,1230,705)|draw_card('dumpL',45,875,1155,740)|draw_card('dumpR',1225,875,1230,740)
finish('09_动力开关与回生泄放',rs,'U24 位于两路泄放之间；功率管及外部电阻预留散热和工具空间。')
start('10 · 两路 5V 过压保护的实际摆放','对应原理图第 08 页的两条 5V 支路 · 两组分别跟随自己的降压电源与 USB 输出')
rs=draw_card('protect5L',45,150,1090,1250)|draw_card('protect5R',1160,150,1095,1250)
finish('10_两路5V过压保护',rs,'Q8/Q10 串在各自功率路径，比较器与分压在旁边安静处。')
start('11 · 3.3V 保护、电池预警与过流比较','对应原理图第 08 页的其余电路 · 分成电源旁的 U29 小组和电流汇合处的 U30 小组')
rs=draw_card('protect3',45,150,1280,1250)|draw_card('overcurrent',1350,150,905,1250)
finish('11_辅助保护与过流比较',rs,'过流基准靠比较器，采样放大器仍保留在采样电阻旁。')
start('12 · 控制与监测接口','对应原理图第 09 页 · 与编码器滤波、安全逻辑、电流比较相邻')
rs=draw_card('control',45,150,1510,1250)
rect(1580,150,675,1250,'#fff',COL['edge'],15,2)
for i,(h,rows) in enumerate([
 ('来自电机侧',['左轮滤波输出 → J1 的 7、8 脚。','右轮滤波输出 → J2 的 2、1 脚。']),
 ('发往控制门',['J1 的 1、2 脚给出左轮控制。','J2 的 5、6 脚给出右轮控制。','先经过 U11，再进入驱动模块。']),
 ('集中监测',['两路电流、急停、解锁、电池预警、','USB 故障和复位状态在 J18 汇合。','各电平按当前原理图连接，不互并。']),
 ('布线次序',['先保证地参考连续，再排信号。','采样线不要贴着功率线长距离并行。','不让电机回流穿过此区。'])]):
 yy=205+i*275;text(h,1610,yy,26,weight=700)
 for z,s in enumerate(rows):text(s,1610,yy+47+z*37,22)
finish('12_控制与监测接口',rs,'预留排针插拔空间；ADC 滤波靠接收接口。')

# Verified existing detailed guides are included rather than regenerated over project files.
old=[('01_电池入口与电源开关','input-layout/电池入口与降压输入_布局示意',{'CN1','F1','Q1','D1','D2','R51','C58','C59','C60','U21','R52','Q3','R53','D3','Q4','R54','C101'},'入口大电流路径、降压输入开关与公共基准。'),
 ('02_电池窗口比较','lm393-layout/U22_U23_布局示意',{'U21','R52','U22','U23','C102','C103',*[f'R{i}' for i in range(55,65)]},'电池窗口分压靠比较器，U21/R52 是和图 01 共用的两颗器件。'),
 ('03_两路5V降压与USB','usb-layout/两路5V与USB供电_布局示意',set(AUDIT['sheets']['02_usb_5v']),'两路降压与两路 USB；中间保护必须用图 10 的实际元件落实。')]
for name,src,refs,summary in old:
 for ext in ['svg','png']:shutil.copyfile(ROOT/'review'/(src+'.'+ext),OUT/(name+'.'+ext))
 PAGES.append(dict(name=name,refs=sorted(refs),summary=summary))
 for r in refs:COVER.setdefault(r,[]).append(name)

# Electrical sequence across sheets, and the physical return-loop priorities.
start('04 · 跨页电源组合与回流路径','原理图页号不决定物理位置：把降压、串联保护与接口组合成完整支路；各支路共用连续地',2500,1650)
def chainbox(x,y,w,title,rows):
 rect(x,y,w,165,'#fff',COL['edge'],12,2);text(title,x+18,y+36,25,weight=700)
 for i,t in enumerate(rows):text(t,x+18,y+78+i*32,22,COL['muted'])
def chainarrow(x1,x2,y,color=COL['power']):
 line([(x1,y),(x2,y)],color,5);arrow(x2,y,1,0,color)
for y,title,parts in [
 (185,'逻辑板 5V：第 02 页 → 第 08 页 → 第 02 页',[
 ('降压核心',['U5 / L1','C4 / C5 输出电容']),('过压开关',['Q8 / Q9 / U27','检测电阻放在旁边']),('端口控制',['U7 / C104 / C105','R65 / R66']),('板边插座',['USB1','插口朝板外'])]),
 (505,'计算板 5V：第 02 页 → 第 08 页 → 第 02 页',[
 ('降压核心',['U1 / L2','C12 / C13 输出电容']),('过压开关',['Q10 / Q11 / U28','检测电阻放在旁边']),('端口控制',['U8 / C106 / C107','R67 / R68']),('板边插座',['USB2','插口朝板外'])]),
 (825,'独立 3.3V：第 03 页 → 第 08 页 → 第 03 页',[
 ('降压核心',['U3 / L3','C110 / C111 输出电容']),('过压开关',['Q12 / Q13 / U29','保护后的输出去跳帽']),('电源选择',['JP1 默认接 1—2','J9 接可选外部输入']),('输出分配',['J14；FB1 → 传感器','C112/C113 与接口去耦'])])]:
 text(title,65,y-20,27,weight=700)
 for i,(t,rows) in enumerate(parts):
  x=65+i*600;chainbox(x,y,520,t,rows)
  if i<3:chainarrow(x+528,x+586,y+81)
 text('先锁住这一整条功率链的位置，再把比较、分压、驱动电阻塞到对应功率器件旁的安静侧。',65,y+215,22)
rect(55,1150,1175,350,'#fff',COL['edge'],12,2)
text('高频回流优先闭合在芯片旁',80,1195,28,weight=700)
for i,s in enumerate(['U5：C3 → 2 脚输入 → 内部开关 → 4 脚地 → C3。',
 'U1 同样围住 C10；U3 同样围住 C108。',
 '输入电容与芯片地之间短而宽，旁边用过孔接到底层。',
 '底层保持连续地；反馈取样靠输出电容，从开关节点外侧绕回。',
 '板框确定后再按电流、铜厚和温升核算铜宽、过孔数量。']):text(s,80,1248+i*45,22)
rect(1260,1150,1175,350,'#fff',COL['edge'],12,2)
text('电机与泄放回流留在动力区',1285,1195,28,weight=700)
for i,s in enumerate(['左轮：C122 正端 → U2 / 电机 → U2 地 → C122 负端。',
 '右轮同理围住 C131；储能与陶瓷电容都靠对应模块。',
 '泄放：本路正端 → 外置电阻 → Q6/Q7 → 本路回流。',
 '采样从 R84/R94 两端单独引出，不能借用功率铜作为测量线。',
 '不要切割地平面来“分地”；用摆放和路径避免电机回流穿过控制区。']):text(s,1285,1248+i*45,22)
finish('04_跨页组合与回流',set(),'三条电源必须按降压、保护、分配的顺序布局，并优先保证高频与电机回流。')

# An overview based on physical zones, deliberately not a made-up board dimension.
start('00 · 整板模块分区与主要连接','先按接口和功率路径定大组，再按后续局部图细化 · 当前无板框，本图表达相对位置，不按整板尺寸比例',2500,1740)
rect(50,155,1780,1390,'#fff','#637d93',22,3)
rect(80,187,1720,435,'#fff4ec',radius=14)
text('动力区：接口、功率管与驱动模块朝板外；留出插拔和散热空间',100,219,24,'#945424',weight=700)
rect(80,677,1720,390,'#edf6fa',radius=14)
text('安静区：比较、基准与控制 · 同一连续地平面，靠布局控制回流',100,710,24,COL['ref'],weight=700)
rect(80,1120,1720,390,'#f0f6ec',radius=14)
text('降压与输出区：每一路按功率流向成链摆放',100,1153,24,COL['ground'],weight=700)

def block(x,y,w,h,title,rows,fill='#fff'):
 rect(x,y,w,h,fill,COL['edge'],10,2);text(title,x+15,y+31,23,weight=700)
 for i,r in enumerate(rows):text(r,x+15,y+65+29*i,19,COL['muted'])
def flow(points,color=COL['power'],dash=''):
 line(points,color,5 if color==COL['power'] else 3,dash);dx=points[-1][0]-points[-2][0];dy=points[-1][1]-points[-2][1];arrow(*points[-1],dx,dy,color)

block(105,260,320,225,'电池入口 / 图 01',['CN1 → F1 → Q1','D1 + C58/C59/C60','插座朝左侧板外','入口后分成动力和降压'])
block(490,260,265,225,'电机开关 / 图 09',['Q2 / Q5 / D4','输出分到两只采样电阻','TP1 留测试空间'])
block(820,260,420,225,'左轮 / 图 07、09',['R84 → U2 → J3','U25 靠 R84；C122/C123 靠模块','Q6 / J16 靠左轮母线','模块与功率管预留散热'])
block(1305,260,450,225,'右轮 / 图 08、09',['R94 → U4 → J4','U26 靠 R94；C131/C132 靠模块','Q7 / J17 靠右轮母线','方向服从接口与两排实际脚位'])
flow([(425,340),(490,340)]);flow([(755,340),(820,340)])
flow([(775,340),(775,238),(1280,238),(1280,340),(1305,340)])
block(490,520,265,90,'公共基准',['U21 / R52 · 图 01、02'])
block(820,520,420,90,'回生比较 U24 · 图 09',['靠两路母线，栅极线从功率侧引出'])
block(1305,520,450,90,'过流比较 U30 · 图 11',['接两路放大后的电流，不拉长检测对线'])
flow([(1030,485),(1030,520)],COL['ref'],'7 5')
flow([(1530,485),(1530,520)],COL['ref'],'7 5')

block(105,755,320,240,'电池窗口 / 图 02',['U22 / U23','取样从入口保护后引入','共享基准沿安静区分配','与热源、电感保持间隔'])
block(490,755,400,240,'急停、锁存、控制门 / 图 06',['J15 → U10 → U12 → U11','控制门位于两轮控制分支处','使能回到 Q2；控制分别去 U2/U4','外部急停插座留板边空间'])
block(955,755,800,110,'编码器与监测 / 图 07、08、12',['滤波靠 J1/J2；J1/J2/J18 朝右侧板外，采样 R124/R125/C143 靠 J18'])
block(955,895,800,100,'传感器端 / 图 05',['J10/J11/J12/J13、J14 朝右侧板外；FB1 后供电，接口旁去耦'])
flow([(425,860),(490,860)],COL['enable']);flow([(890,820),(955,820)],COL['enable'],'6 5')
flow([(680,755),(680,653),(1160,653),(1160,485)],COL['enable'])
flow([(1160,653),(1670,653),(1670,485)],COL['enable'])
flow([(1520,610),(1520,630),(910,630),(910,737),(780,737),(780,755)],COL['enable'],'6 5')

block(105,1190,265,215,'降压输入 / 图 01',['Q3 / Q4 / C101','降压支路单独引出','不穿越控制区','三路输入各自就近去耦'])
block(435,1190,420,215,'逻辑板 5V / 图 03、10',['U5 / L1 → Q8 / U27','→ U7 → USB1','降压、保护、端口串成一列','USB 插座朝下侧板外'])
block(920,1190,420,215,'计算板 5V / 图 03、10',['U1 / L2 → Q10 / U28','→ U8 → USB2','与另一条 5V 分别布线','USB 插座朝下侧板外'])
block(1405,1190,350,215,'独立 3.3V / 图 05、11',['U3 / L3 → Q12 / U29','→ JP1 → 辅助与传感器','J9 为外部可选输入','跳帽默认选择板载电源'])
flow([(265,485),(265,635),(65,635),(65,1092),(235,1092),(235,1190)])
flow([(370,1290),(435,1290)]);flow([(390,1290),(390,1100),(1580,1100),(1580,1190)])
flow([(1130,1100),(1130,1190)]);flow([(1650,1190),(1650,1060),(1590,1060),(1590,995)])
text('USB1',645,1465,26,anchor='middle',weight=700);flow([(645,1405),(645,1490)])
text('USB2',1130,1465,26,anchor='middle',weight=700);flow([(1130,1405),(1130,1490)])

rect(1860,155,590,1390,'#fff',COL['edge'],16,2)
notes=[('先锁定接口',['先定电池、电机、USB、控制、','传感器和急停的出线方向。','整组可以旋转；不要只转芯片。']),('再放功率链',['入口后就近分支，左右电机各自','保留短供电与短回流。','两路 5V 保护随各自输出摆放。']),('然后放敏感电路',['采样放大器贴采样电阻；','比较器接收放大后的信号。','基准、分压与编码器避开热区。']),('最后细化外围',['先去耦和开关小回路，再反馈、','门极、信号与测试空间。','逐项参考后面的真实封装图。']),('地与热的处理',['地仍是同一个网络，避免割裂。','高电流回路在功率区就近闭合，','不借用控制区细线回地。']),('图的边界',['整板分区是本项目的布局建议；','芯片关键外围优先参考手册。','板框、安装孔与铜宽仍须落实。'])]
for i,(h,rows) in enumerate(notes):
 yy=207+i*219;text(h,1887,yy,26,weight=700)
 for z,s in enumerate(rows):text(s,1887,yy+43+z*34,22)
text('红线：供电路径    紫线：安全与控制关系    蓝虚线：检测关系；仅展示主要联系，其余连接按网表落实。',70,1600,24,COL['ink'])
finish('00_整板模块布局总图',set(),'整板优先按接口、功率路径、安静控制区安排，再展开各局部组。')

# Coverage: U11 is one physical chip; U21/R52 appear twice intentionally in reused reference drawings.
assert set(COVER)==set(FP),(sorted(set(FP)-set(COVER)),sorted(set(COVER)-set(FP)))
assert len(FP)==211
assert not any(c['courtyard_box_overlaps'] for c in CHECKS),'New local placement groups overlap.'
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
assert after==HASHES,'Source changed while generating; do not overwrite user work.'
PAGES.sort(key=lambda p:p['name'])
result=dict(date='2026-10-04',physical_components=len(FP),schematic_pages=len(AUDIT['sheets']),all_refs_covered=True,coverage=COVER,groups=PLAN,courtyard_checks=CHECKS,verified_key_connections=LINKS,source_hashes_before=HASHES,source_hashes_after=after,source_unchanged=True,pcb_layers=AUDIT['layers'],pcb_outline_present=bool(AUDIT['edge']),pages=PAGES)
(OUT/'绘图核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'元件布局索引.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['位号','数值或型号','封装','原理图页','布局图','局部组','局部X毫米','局部Y毫米','KiCad角度度'])
 for r in sorted(FP):
  gs=[(g,p[r]) for g,p in PLAN.items() if r in p]
  g,co=gs[0] if gs else ('见既有局部图',('','',''))
  w.writerow([r,COMP[r].findtext('value'),COMP[r].findtext('footprint'),'/'.join(s for s,rr in AUDIT['sheets'].items() if r in rr),'/'.join(COVER[r]),g,*co])
print(json.dumps({'pages':len(PAGES),'coverage':len(COVER),'new_groups':len(PLAN),'key_links':len(LINKS),'overlaps':[c for c in CHECKS if c['courtyard_box_overlaps']]},ensure_ascii=False))
