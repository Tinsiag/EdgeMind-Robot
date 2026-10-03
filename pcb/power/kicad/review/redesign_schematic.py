"""Rebuild the schematic only; keep the board and its old libraries byte-for-byte.

Native KiCad symbols, explicit local wiring, global labels across functional pages.
All coordinates are mm. Run with the bundled Python; validate with kicad-cli.
"""
from pathlib import Path
import copy, json, re, math, uuid, hashlib
from collections import defaultdict, Counter
from kicad_tools import parse, Node, Atom, child, children, val, prop

ROOT = Path(__file__).resolve().parents[1]
STEM = 'ProPrj_power_2026-10-02'
STD = Path(r'D:\KiCad\10.0\share\kicad')
ROOT_ID = '734fd4e0-a6e1-4cb5-8348-642b7ec58253'
EXPECTED_BOARD = 'b1f0ae58f0c056b78fcf4b2b0c4fc0f67e39ae8b1f3ccb8ed98e1bcf4ab4488d'
CUSTOM = {}
LIBS = {}
USED = set()
COUNTS = {'R': 19, 'C': 69, 'U': 8, 'J': 8, 'D': 1, 'Q': 1, 'L': 3,
          'RV': 0, 'TP': 0, 'F': 0, '#PWR': 100, '#FLG': 100}
COMPONENTS = []
RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0603_1608Metric'
C8FP='Capacitor_SMD:C_0805_2012Metric'
SO8='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
SO14='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
SOT5='Package_TO_SOT_SMD:SOT-23-5'
TO220='Package_TO_SOT_THT:TO-220-3_Vertical'
IND='Inductor_SMD:L_Coilcraft_XAL7030-472'
ELCAP='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm'
TERM='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
USBFP='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'
EFUSEFP='Package_DFN_QFN:Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias'
USBICFP='Package_DFN_QFN:Texas_RVC0020A_WQFN-20-1EP_3x4mm_P0.5mm_EP1.6x2.6mm'

def q(v): return json.dumps(str(v), ensure_ascii=False)
def snap(v): return round(round(float(v)/1.27)*1.27,5)
def num(v): return str(round(float(v),5)).rstrip('0').rstrip('.') if '.' in str(round(float(v),5)) else str(v)
def uid(key): return str(uuid.uuid5(uuid.NAMESPACE_URL,'edgemind:schematic-r2:'+key))
def effects(size=1.0, hide=False, justify=''):
    return f'(effects (font (size {size} {size}))'+(' (hide yes)' if hide else '')+(f' (justify {justify})' if justify else '')+')'

def serialize_tree(n, source=None, level=0):
    if not isinstance(n,(list,Node)):
        if isinstance(n,Atom) and source is not None:
            raw=source[n.start:n.end]
            return q(n) if raw.startswith('"') else str(n)
        return str(n)
    if all(not isinstance(x,(list,Node)) for x in n):
        return '('+' '.join(serialize_tree(x,source,level+1) for x in n)+')'
    s='('+serialize_tree(n[0],source,level+1)
    for x in n[1:]:
        s+= ('\n'+'\t'*(level+1) if isinstance(x,(list,Node)) else ' ')+serialize_tree(x,source,level+1)
    return s+')'

def std_symbol(lib_id):
    if lib_id in CUSTOM:return CUSTOM[lib_id]
    lib,name=lib_id.split(':')
    if lib not in LIBS:
        source=(STD/'symbols'/(lib+'.kicad_sym')).read_text(encoding='utf-8')
        root=parse(source)
        LIBS[lib]=(source,{str(s[1]):s for s in children(root,'symbol')})
    source,allsyms=LIBS[lib]
    s=allsyms[name]
    parent=val(s,'extends')
    if parent:
        base=std_symbol(lib+':'+parent)
        flat=copy.deepcopy(base)
        flat[1]=q(name)
        # Serialize/parse the inherited body so quoted replacement names remain quoted.
        for node in children(flat,'symbol'):
            old=str(node[1]).strip('"')
            node[1]=q(name+old[old.rfind('_',0,old.rfind('_')):])
        for p in children(s,'property'):
            old=next((x for x in children(flat,'property') if str(x[1]).strip('"')==p[1]),None)
            if old:flat.remove(old)
            flat.append(parse(serialize_tree(p,source)))
        return parse(serialize_tree(flat, None))
    # Preserve atom quoting explicitly, including inherited symbol properties.
    return parse(serialize_tree(s,source))

def symbol_text(lib_id):
    s=std_symbol(lib_id)
    source=serialize_with_quotes(s)
    return re.sub(r'^\(symbol\s+"[^"]+"','(symbol '+q(lib_id),source,count=1)

def serialize_with_quotes(n):
    """All parsed atoms remember whether they originated as quoted tokens."""
    if not isinstance(n,(list,Node)):
        return getattr(n,'raw',None) or str(n)
    return '('+' '.join(serialize_with_quotes(x) for x in n)+')'

def capture_raw(text):
    n=parse(text)
    def walk(x):
        if isinstance(x,Atom):x.raw=text[x.start:x.end]
        elif isinstance(x,(list,Node)):
            for a in x:walk(a)
    walk(n)
    return n

# Resolve inheritance once with raw token preservation.
def resolved(lib_id):
    if lib_id in CUSTOM:return capture_raw(CUSTOM[lib_id])
    lib,name=lib_id.split(':')
    if lib not in LIBS:
        txt=(STD/'symbols'/(lib+'.kicad_sym')).read_text(encoding='utf-8')
        rt=capture_raw(txt)
        LIBS[lib]=(txt,{str(s[1]):s for s in children(rt,'symbol')})
    s=LIBS[lib][1][name]
    base=val(s,'extends')
    if not base:return capture_raw(serialize_with_quotes(s))
    flat=resolved(lib+':'+base)
    flat[1]=capture_raw('(x '+q(name)+')')[1]
    for n in children(flat,'symbol'):
        suffix=re.search(r'(_\d+_\d+)$',str(n[1])).group(1)
        n[1]=capture_raw('(x '+q(name+suffix)+')')[1]
    for p in children(s,'property'):
        old=next((p0 for p0 in children(flat,'property') if p0[1]==p[1]),None)
        if old:flat.remove(old)
        flat.append(capture_raw(serialize_with_quotes(p)))
    return flat

def cached(lib_id):
    s=resolved(lib_id)
    s[1]=capture_raw('(x '+q(lib_id)+')')[1]
    return serialize_with_quotes(s)

def custom_symbol(name,ref,pins,box=(-10.16,15.24,10.16,-15.24),description='',fp='',datasheet=''):
    x1,y1,x2,y2=box
    body=[f'(symbol {q(name)} (pin_names (offset 0.8)) (in_bom yes) (on_board yes)',
      f'(property "Reference" {q(ref)} (at 0 {y1+2.54} 0) {effects(1.27)})',
      f'(property "Value" {q(name)} (at 0 {y2-2.54} 0) {effects(1.27)})',
      f'(property "Footprint" {q(fp)} (at 0 0 0) {effects(hide=True)})',
      f'(property "Datasheet" {q(datasheet)} (at 0 0 0) {effects(hide=True)})',
      f'(property "Description" {q(description)} (at 0 0 0) {effects(hide=True)})',
      f'(symbol {q(name+"_0_1")} (rectangle (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.254) (type default)) (fill (type background))))',
      f'(symbol {q(name+"_1_1")}']
    for pin,name0,typ,x,y,a in pins:
        body.append(f'(pin {typ} line (at {x} {y} {a}) (length 5.08) (name {q(name0)} {effects(1.0)}) (number {q(pin)} {effects(1.0)}))')
    body.append('))')
    CUSTOM['EdgeMind_Power:'+name]='\n'.join(body)

custom_symbol('MP2236GJ-Z','U',[
 ('2','IN','power_in',-15.24,7.62,0),('6','EN','input',-15.24,0,0),
 ('7','VCC','power_out',-15.24,-7.62,0),('1','AGND','power_in',-2.54,-20.32,90),
 ('4','GND','power_in',2.54,-20.32,90),('3','SW','power_out',15.24,7.62,180),
 ('5','BST','passive',15.24,2.54,180),('8','FB','input',15.24,-7.62,180)],
 description='MPS 3-18V synchronous buck; pin map verified against MP2236 datasheet',fp='Package_TO_SOT_SMD:TSOT-23-8',
 datasheet='https://www.monolithicpower.com/en/mp2236.html')
custom_symbol('AT8236_Dual_Module','U',[
 ('12','AIN1','input',-15.24,10.16,0),('11','AIN2','input',-15.24,5.08,0),
 ('3','BIN1','input',-15.24,0,0),('4','BIN2','input',-15.24,-5.08,0),
 ('2','AOUT1','output',15.24,10.16,180),('1','AOUT2','output',15.24,5.08,180),
 ('13','BOUT1','output',15.24,0,180),('14','BOUT2','output',15.24,-5.08,180),
 ('5','VCC_REF','input',-5.08,20.32,270),('10','VCC_REF','passive',-5.08,20.32,270),
 ('6','VM','power_in',0,20.32,270),('9','VM','passive',0,20.32,270),
 ('7','GND','power_in',0,-20.32,90),('8','GND','passive',0,-20.32,90)],
 box=(-10.16,15.24,10.16,-15.24),description='Two 1x7 female sockets; left top-to-bottom 1..7, right top-to-bottom 8..14. VCC is current-limit reference, not a supply output.')
custom_symbol('TPS25940L','U',[
 *[(str(k),'IN','power_in' if k==9 else 'passive',-15.24,10.16,0) for k in range(9,14)],
 *[(str(k),'OUT','power_out' if k==4 else 'passive',15.24,10.16,180) for k in range(4,9)],
 ('14','EN_UVLO','input',-15.24,2.54,0),('15','OVP','input',-15.24,-5.08,0),
 ('1','DEVSLP','input',-15.24,-12.7,0),('3','PGTH','input',-5.08,22.86,270),
 ('2','PGOOD','open_collector',15.24,5.08,180),('20','FLT_N','open_collector',15.24,0,180),
 ('19','IMON','output',15.24,-5.08,180),('17','ILIM','passive',15.24,-12.7,180),
 ('18','dVdT','passive',15.24,-17.78,180),('16','GND','power_in',0,-22.86,90),
 ('21','GND_EP','passive',0,-22.86,90)],box=(-10.16,17.78,10.16,-17.78),
 description='TI TPS25940L: programmable OV cutoff, true reverse blocking and latched thermal fault; pin map from original TI datasheet',
 fp=USBICFP,datasheet='https://www.ti.com/lit/ds/symlink/tps25940.pdf')

class Schematic:
    def __init__(self,file,title,index,paper='A3'):
        self.file=file;self.title=title;self.index=index;self.paper=paper
        self.id=ROOT_ID if index==1 else uid(file)
        self.path='/'+ROOT_ID if index==1 else '/'+ROOT_ID+'/'+uid('sheet:'+file)
        self.items=[];self.lib=set();self.seq=0;self.wires=set();self.junctions=set()
    def uuid(self,what):self.seq+=1;return uid(self.file+':'+what+':'+str(self.seq))
    def text(self,t,x,y,size=1.27):
        self.items.append(f'(text {q(t)} (at {num(x)} {num(y)} 0) {effects(size,justify="left")} (uuid {q(self.uuid("text"))}))')
    def box(self,x,y,w,h,title):
        self.items.append(f'(rectangle (start {x} {y}) (end {x+w} {y+h}) (stroke (width 0.254) (type default)) (fill (type none)) (uuid {q(self.uuid("box"))}))')
        self.text(title,x+3,y+5,1.52)
    def wire(self,*pts):
        for a,b in zip(pts,pts[1:]):
            a=tuple(snap(t) for t in a);b=tuple(snap(t) for t in b)
            if a==b:continue
            assert a[0]==b[0] or a[1]==b[1], (a,b)
            key=tuple(sorted((a,b)))
            if key in self.wires:continue
            self.wires.add(key)
            self.items.append(f'(wire (pts (xy {num(a[0])} {num(a[1])}) (xy {num(b[0])} {num(b[1])})) (stroke (width 0) (type default)) (uuid {q(self.uuid("wire"))}))')
    def dot(self,p):
        p=tuple(snap(x) for x in p)
        if p in self.junctions:return
        self.junctions.add(p)
        self.items.append(f'(junction (at {num(p[0])} {num(p[1])}) (diameter 0) (color 0 0 0 0) (uuid {q(self.uuid("dot"))}))')
    def label(self,name,p,angle=0,kind='global_label'):
        p=tuple(snap(x) for x in p)
        self.items.append(f'({kind} {q(name)} (shape passive) (at {num(p[0])} {num(p[1])} {angle}) {effects(1.0,justify="left" if angle==0 else "right")} (uuid {q(self.uuid("label"))})'+
          (f' (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {num(p[0])} {num(p[1])} {angle}) {effects(hide=True)})' if kind=='global_label' else '')+')')
    def stub(self,c,pin,name,length=7.62):
        p=c.pin(pin);a=c.angles[str(pin)]
        dx={0:-length,180:length,90:0,270:0}[a]
        dy={0:0,180:0,90:length,270:-length}[a]
        end=(p[0]+dx,p[1]+dy);self.wire(p,end);self.label(name,end,0 if dx>=0 else 180)
        return end
    def nc(self,c,pin):
        p=c.pin(pin)
        self.items.append(f'(no_connect (at {num(p[0])} {num(p[1])}) (uuid {q(self.uuid("nc"))}))')
    def sym(self,lib_id,ref,x,y,value=None,fp=None,angle=0,unit=1,desc='',datasheet=None,mpn=None,dnp=False,on_board=True):
        x,y=snap(x),snap(y)
        if ref is None:
            prefix=prop(resolved(lib_id),'Reference')
            COUNTS[prefix]=COUNTS.get(prefix,0)+1;ref=prefix+str(COUNTS[prefix])
        if ref.startswith('#'):value=value or prop(resolved(lib_id),'Value')
        else:
            key=(ref,unit)
            assert key not in USED,key
            USED.add(key)
        s=resolved(lib_id);self.lib.add(lib_id)
        value=value or lib_id.split(':')[1]
        fp=prop(s,'Footprint') if fp is None else fp
        datasheet=prop(s,'Datasheet') if datasheet is None else datasheet
        c=Component(self,lib_id,ref,x,y,angle,unit,s)
        propvals={'Reference':ref,'Value':value,'Footprint':fp,'Datasheet':datasheet,'Description':desc or prop(s,'Description')}
        if lib_id.startswith('Device:') and ' ' in value:propvals['Specification']=value
        if mpn:propvals['MPN']=mpn
        body=[f'(symbol (lib_id {q(lib_id)}) (at {num(x)} {num(y)} {angle}) (unit {unit}) (in_bom {"no" if ref.startswith("#") else "yes"}) (on_board {"no" if ref.startswith("#") or not on_board else "yes"}) (dnp {"yes" if dnp else "no"}) (uuid {q(uid("component:"+ref+":"+str(unit)))}))']
        body[0]=body[0][:-1]
        small=lib_id.startswith('Device:') or lib_id.startswith('Jumper:')
        for name,v in propvals.items():
            hide=name not in ['Reference','Value'] or ref.startswith('#')
            px=x+3.0 if small and angle==0 else x
            py=y+(-1.3 if name=='Reference' else 1.3) if small and angle==0 else y+(-5.08 if name=='Reference' else -2.54)
            if not small and name in ['Reference','Value']:
                if lib_id.startswith(('74','Comparator:','Power_Management:','Interface_USB:','Power_Supervisor:')):
                    pn=next(t for t in children(s,'property') if t[1]==name);at=child(pn,'at');lx,ly=map(float,at[1:3]);aa=math.radians(angle)
                    px=x+lx*math.cos(aa)-ly*math.sin(aa);py=y-lx*math.sin(aa)-ly*math.cos(aa)
                else:py=y-19.05 if name=='Reference' else y-16.51
                if lib_id.startswith('Connector_Generic:'):
                    px=x+5.08;py=min(t[1] for t in c.pins.values())-(6.35 if name=='Reference' else 3.81)
                if lib_id.startswith('Reference_Voltage:'):px=x+13.97;py=y-2.54 if name=='Reference' else y
                if lib_id.startswith('Transistor_FET:'):px=x+13.97;py=y-10.16 if name=='Reference' else y-7.62
                if lib_id.startswith('Transistor_BJT:'):px=x+13.97;py=y-2.54 if name=='Reference' else y
                if lib_id=='EdgeMind_Power:AO4409':px=x+16.51;py=y-10.16 if name=='Reference' else y-7.62
                if lib_id.startswith('Reference_Voltage:'):px=x+18.415;py=y+6.35 if name=='Reference' else y+8.89
            if small and name=='Value':
                if lib_id=='Device:L':v=value.split()[0]
                elif lib_id.startswith('Device:C'):
                    v='/'.join(value.split()[:2])
                elif lib_id=='Device:R':v=value.replace(' ','/')
                elif lib_id=='Device:Fuse':
                    current=value.split()[0]
                    v=(current+' / MINI 插片保险丝') if 'MINI' in value else (current+' 慢断保险丝 / 5×20mm') if '5x20' in value else value
                elif lib_id=='Device:R_Potentiometer':v='10k/3296W'
            if small and angle in [90,270]:py=y-10.16 if name=='Reference' else y-6.35
            if lib_id=='EdgeMind_Power:AT8236_Dual_Module' and name in ['Reference','Value']:
                px=x+24.13;py=y-25.4 if name=='Reference' else y-22.86
            if lib_id=='EdgeMind_Power:74HC08' and name in ['Reference','Value']:
                px=x+(15.24 if unit==5 else 0)
                py=y-((5.08 if name=='Reference' else 2.54) if unit==5 else (10.16 if name=='Reference' else 7.62))
            if lib_id=='Connector:USB_C_Receptacle_PowerOnly_6P' and name in ['Reference','Value']:
                px=x;py=y+(26.67 if name=='Reference' else 29.21)
            if lib_id=='Device:D_Zener' and angle in [90,270] and name in ['Reference','Value']:
                px=x+7.62;py=y-(2.54 if name=='Reference' else 0)
            fieldangle=0 if angle==180 else angle
            body.append(f'(property {q(name)} {q(v)} (at {num(px)} {num(py)} {fieldangle}) {effects(0.9 if name=="Value" else 1.0,hide, "left" if small and angle==0 else "")} )')
        for pin in c.pins:
            body.append(f'(pin {q(pin)} (uuid {q(uid("pin:"+ref+":"+str(unit)+":"+pin))}))')
        body.append(f'(instances (project {q(STEM)} (path {q(self.path)} (reference {q(ref)}) (unit {unit})))) )')
        self.items.append('\n'.join(body))
        COMPONENTS.append({'sheet':self.file,'reference':ref,'unit':unit,'value':value,'footprint':fp,'lib_id':lib_id,'mpn':mpn,'datasheet':datasheet,'dnp':dnp,'on_board':on_board and not ref.startswith('#')})
        return c
    def ground(self,p,length=3.81):
        end=(p[0],p[1]+length);self.wire(p,end)
        return self.sym('power:GND',None,*end,fp='')
    def flag(self,name,p):
        self.label(name,p);self.sym('power:PWR_FLAG',None,*p,fp='')
    def finish(self):
        # Native cleanup can merge collinear segments. Every intentional T must
        # retain an explicit junction so the endpoint stays connected after save.
        for a,b in self.wires:
            for point in (a,b):
                if any(c[0]==d[0]==point[0] and min(c[1],d[1])<point[1]<max(c[1],d[1])
                       or c[1]==d[1]==point[1] and min(c[0],d[0])<point[0]<max(c[0],d[0])
                       for c,d in self.wires):
                    self.dot(point)
        data=['(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")',
          f'(uuid {q(self.id)}) '+('(paper "User" 420 320)' if self.paper=='User' else '(paper "User" 420 370)' if self.paper=='Overview' else f'(paper {q(self.paper)})'),
          f'(title_block (title {q(self.title)}) (date "2026-10-03") (rev "R2 schematic") (company "EdgeMind Robot") (comment 1 "Schematic redesign only - PCB intentionally unchanged"))',
          '(lib_symbols '+'\n'.join(cached(k) for k in sorted(self.lib))+')']
        data+=self.items
        if self.index==1:data.append('(sheet_instances (path "/" (page "1")))')
        data.append('(embedded_fonts no))')
        (ROOT/self.file).write_text('\n'.join(data)+'\n',encoding='utf-8')

class Component:
    def __init__(self,page,lib_id,ref,x,y,angle,unit,s):
        self.page,self.ref,self.pos,self.unit=page,ref,(x,y),unit
        self.pins={};self.angles={}
        for sub in children(s,'symbol'):
            su,style=map(int,re.search(r'_(\d+)_(\d+)$',str(sub[1])).groups())
            if su not in (0,unit) or style not in (0,1):continue
            for p in children(sub,'pin'):
                a=child(p,'at');lx,ly,pa=map(float,a[1:4]);ra=math.radians(angle)
                dx=lx*math.cos(ra)-ly*math.sin(ra);dy=lx*math.sin(ra)+ly*math.cos(ra)
                pin=val(p,'number');self.pins[pin]=(round(x+dx,5),round(y-dy,5));self.angles[pin]=int((pa+angle)%360)
    def pin(self,n):return self.pins[str(n)]

def R(p,x,y,v,ref=None,a=0,**kw):return p.sym('Device:R',ref,x,y,v,RFP,angle=a,**kw)
def C(p,x,y,v='100nF 50V',ref=None,a=0,fp=CFP,**kw):return p.sym('Device:C',ref,x,y,v,fp,angle=a,**kw)
def cap(p,x,y,net,value,ref=None,polar=False,bus=None):
    c=p.sym('Device:C_Polarized' if polar else 'Device:C',ref,x,y,value,ELCAP if polar else C8FP)
    if bus:p.wire(c.pin(1),bus);p.dot(bus)
    else:p.stub(c,1,net,3.81)
    p.ground(c.pin(2));return c
def pull(p,x,y,net,value='10k',to='+3V3'):
    r=R(p,x,y,value);p.stub(r,1,to,3.81);p.stub(r,2,net,3.81);return r
def down(p,x,y,net,value='10k'):
    r=R(p,x,y,value);p.stub(r,1,net,3.81);p.ground(r.pin(2));return r
def hdr(p,x,y,n,ref,value,fp=None,a=0,nets=None):
    fp=fp or f'Connector_PinHeader_2.54mm:PinHeader_1x{n:02d}_P2.54mm_Vertical'
    h=p.sym(f'Connector_Generic:Conn_01x{n:02d}',ref,x,y,value,fp,angle=a)
    if nets:
        for k,name in enumerate(nets,1):
            if name is None:p.nc(h,k)
            else:p.stub(h,k,name,5.08)
    return h
def tp(p,x,y,net):
    c=p.sym('Connector:TestPoint',None,x,y,net,'TestPoint:TestPoint_Pad_D2.0mm')
    p.stub(c,1,net,3.81);return c
def decouple(p,x,y,rail='+3V3'):
    return cap(p,x,y,rail,'100nF 50V')

def e_fuse(p,x,y,rail,ref=None,limit='7.15k',uvtop='75.0k',enable='MOTOR_ARMED',automatic=False):
    u=p.sym('Power_Management:TPS26630RGE',ref,x,y,'TPS26630RGER',EFUSEFP,
      desc='Programmable UV/OV, bus current monitor, latch-off overload response',mpn='TPS26630RGER')
    pin=u.pin
    # Shared IN/IN_SYS with local input bypass; no external blocking FET.
    vin=(x-24.13,y-12.7);p.wire(pin(1),vin,(vin[0],y-28));p.label('VBAT_SYS',(vin[0],y-28),180)
    p.wire(pin(5),(x,y-28),(vin[0],y-28));p.dot((vin[0],y-28))
    ci=C(p,x-31.75,y-5.08,'100nF 50V');p.wire(ci.pin(1),(ci.pin(1)[0],vin[1]),vin);p.dot(vin);p.ground(ci.pin(2))
    for k in [3,4,11,16,19,20,21,22,23,24]:p.nc(u,k)
    p.text('MODE open: latch-off',x-17,y+30,0.9)
    # UVLO rising 1.2V, falling 1.122V. Motors 10.2V on/9.54V off;
    # logic 9.636V on/9.01V off. OVP 14.04V nominal.
    for k,xx,yy,top,bottom in [(6,x-62.23,y+2.54,uvtop,'10.0k'),(7,x-46.99,y+25.4,'107k','10.0k')]:
        rt=R(p,xx,yy-10.16,top);rb=R(p,xx,yy+10.16,bottom)
        mid=(xx,yy);p.wire(rt.pin(2),mid,rb.pin(1))
        if k==6:p.wire(mid,pin(k))
        else:p.wire(mid,(x-36.83,yy),(x-36.83,pin(k)[1]),pin(k))
        p.dot(mid)
        p.stub(rt,1,'VBAT_SYS',3.81);p.ground(rb.pin(2),2.54)
    p.stub(u,12,enable,12.7)
    p.ground(pin(8))
    # Pin 25 is coincident with GND 8; hidden stacked pins connect automatically.
    out=(x+29.21,y-12.7);p.wire(pin(17),out);p.label(rail,out)
    p.stub(u,15,'GND',3.81)
    # PGTH=GND disables fast restart, PGOOD is intentionally unused.
    cd=C(p,x+34.29,y+23,'100nF 50V');rl=R(p,x+46.99,y+17.92,limit)
    p.wire(pin(9),(cd.pin(1)[0],pin(9)[1]),cd.pin(1));p.ground(cd.pin(2))
    p.wire(pin(10),(rl.pin(1)[0],pin(10)[1]),rl.pin(1));p.ground(rl.pin(2))
    imon=rail+'_IMON';fault=rail+'_FLT_N'
    p.stub(u,13,imon,7.62);p.stub(u,14,fault,7.62)
    down(p,x+62.23,y+10.16,imon,'10k')
    pull(p,x+62.23,y-15.24,fault)
    p.text('IMON ~0.279V/A (bus current)',x-12,y+36,0.95)
    if automatic:
        # Logic survives motor E-stop; external service enable is 3.3V from 2.5V raw shunt reference.
        pass
    return u

def buck5(p,y,uref,lref,cinput,coutput,rboot,cboot,cvcc,rtop,rbot,cff,out,usbref,icref):
    x=86.36
    p.box(15,y-47,205,120,out+' / MP2236 5.15V (USB source 3A)')
    u=p.sym('EdgeMind_Power:MP2236GJ-Z',uref,x,y,'MP2236GJ-Z','Package_TO_SOT_SMD:TSOT-23-8',mpn='MP2236GJ-Z')
    pin=u.pin
    left=(35.56,pin(2)[1]);p.wire(left,pin(2));p.label('VLOGIC_IN',left,180)
    for i,ref in enumerate(cinput):
        xx=38.1+i*12.7;c=C(p,xx,y+2.54,'22uF 25V X5R',ref,fp=C8FP)
        p.wire(c.pin(1),(xx,left[1]));p.dot((xx,left[1]));p.ground(c.pin(2))
    # Enable from protected input, rather than the previous misleading 300k/130k UV divider.
    re=R(p,58.42,y+20.32,'100k',a=90)
    p.stub(re,1,'VLOGIC_IN',3.81);p.wire(re.pin(2),(67.31,y+20.32),(67.31,y),pin(6))
    cc=C(p,35.56,y+31.75,'1uF 25V',cvcc,fp=C8FP)
    p.wire(pin(7),(43.18,pin(7)[1]),(43.18,cc.pin(1)[1]),cc.pin(1));p.ground(cc.pin(2))
    p.wire(pin(1),(pin(1)[0],y+25.4),(pin(4)[0],y+25.4),pin(4));p.ground((x,y+25.4));p.dot((x,y+25.4))
    l=p.sym('Device:L',lref,132.08,pin(3)[1],'4.7uH XAL7030-472',IND,angle=90,mpn='XAL7030-472MEC')
    p.wire(pin(3),l.pin(1));outpt=(205.74,pin(3)[1]);p.wire(l.pin(2),outpt);p.flag(out,outpt)
    rb=R(p,127,y-31.75,'10R',rboot,a=90)
    cb=C(p,144.78,y-20.32,'100nF 50V',cboot)
    p.wire(pin(5),(109.22,pin(5)[1]),(109.22,y-31.75),rb.pin(1));p.wire(rb.pin(2),(144.78,y-31.75),cb.pin(1))
    p.wire(cb.pin(2),(144.78,y-12.7),(116.84,y-12.7),(116.84,pin(3)[1]));p.dot((116.84,pin(3)[1]))
    for i,ref in enumerate(coutput):
        xx=193.04+i*12.7;co=C(p,xx,y+20.32,'22uF 25V X5R',ref,fp=C8FP)
        p.wire(co.pin(1),(xx,outpt[1]));p.dot((xx,outpt[1]));p.ground(co.pin(2))
    rt=R(p,165.1,y+5.08,'83.5k 0.1%',rtop)
    rr=R(p,165.1,y+30.48,'11.0k 0.1%',rbot)
    mid=(165.1,y+17.78);p.wire(rt.pin(1),(165.1,outpt[1]));p.dot((165.1,outpt[1]))
    p.wire(rt.pin(2),mid,rr.pin(1));p.wire(pin(8),(149.86,pin(8)[1]),(149.86,mid[1]),mid);p.dot(mid);p.ground(rr.pin(2))
    cf=C(p,177.8,y+5.08,'220pF C0G',cff)
    p.wire(cf.pin(1),(177.8,outpt[1]));p.dot((177.8,outpt[1]));p.wire(cf.pin(2),(177.8,mid[1]),mid)
    # Port controller and connector. Both CC wires and switched VBUS are physical wires.
    ux=279.4;uy=y+5.08
    ic=p.sym('Interface_USB:TPS25810RVC',icref,ux,uy,'TPS25810RVCR',USBICFP,mpn='TPS25810RVCR')
    vin=(245.11,ic.pin(2)[1]);p.wire(vin,ic.pin(2));p.label(out+'_PROT',vin,180)
    p.wire(ic.pin(4),(253.99,ic.pin(4)[1]),(253.99,vin[1]));p.dot((253.99,vin[1]))
    p.wire(ic.pin(5),(ux,uy-31.75),(253.99,uy-31.75),(253.99,vin[1]));p.dot((253.99,vin[1]))
    for k,xx in [(6,245.11),(7,237.49),(8,229.87)]:
        p.wire(ic.pin(k),(xx,ic.pin(k)[1]),(xx,uy-31.75),(253.99,uy-31.75));p.dot((xx,uy-31.75))
    ci=p.sym('Device:C_Polarized',None,245.11,uy+33.02,'150uF 10V low-ESR',ELCAP)
    p.wire(ci.pin(1),(222.25,ci.pin(1)[1]),(222.25,vin[1]),vin);p.ground(ci.pin(2));p.dot(vin)
    cref=C(p,257.81,uy+33.02,'100nF 25V')
    p.wire(cref.pin(1),(253.99,cref.pin(1)[1]),(253.99,vin[1]));p.ground(cref.pin(2));p.dot((253.99,vin[1]))
    rf=R(p,254,uy+13.97,'100k 1%')
    p.wire(ic.pin(10),(254,ic.pin(10)[1]),rf.pin(1));p.wire(rf.pin(2),(254,uy+22.86),(261.62,uy+22.86),(261.62,ic.pin(9)[1]),ic.pin(9))
    p.ground(ic.pin(12))
    con=p.sym('Connector:USB_C_Receptacle_USB2.0_16P',usbref,355.6,uy-27.94,out.replace('+','')+' USB-C',USBFP,angle=180)
    vbus=usbref+'_VBUS'
    p.wire(ic.pin(14),con.pin('A4'));p.label(vbus,(315,ic.pin(14)[1]))
    co=C(p,312.42,uy+27.94,'6.8uF 10V X7R',fp=C8FP)
    p.wire(co.pin(1),(312.42,ic.pin(14)[1]));p.dot((312.42,ic.pin(14)[1]));p.ground(co.pin(2))
    for cc,cp,xx in [(11,'A5',325.12),(13,'B5',332.74)]:
        p.wire(ic.pin(cc),(xx,ic.pin(cc)[1]),(xx,con.pin(cp)[1]),con.pin(cp))
    p.ground(con.pin('A1'));p.ground(con.pin('SH'))
    for k in ['A6','A7','A8','B6','B7','B8']:p.nc(con,k)
    for k in [16,17,18,19,20]:p.nc(ic,k)
    p.stub(ic,1,usbref+'_FLT_N',12.7);pull(p,307.34,uy-25.4,usbref+'_FLT_N')
    p.text('IN1=IN2=AUX; EN/CHG/CHG_HI=HIGH\nCC current advertisement: 3A; no external Rp\nVBUS is switched only after valid sink attachment',233.68,y+65,1.0)

def module_fp(row):
    name=f'AT8236_Dual_PinSocket_2x7_P2.54_Row{row:.4f}mm'
    path=ROOT/'EdgeMind_Module.pretty'/(name+'.kicad_mod');path.parent.mkdir(exist_ok=True)
    src=(STD/'footprints'/'Connector_PinSocket_2.54mm.pretty'/'PinSocket_1x07_P2.54mm_Vertical.kicad_mod').read_text(encoding='utf-8')
    tree=capture_raw(src)
    # Copy exact stock socket geometry and model twice, adjusting right pad names.
    body=[f'(footprint {q(name)} (version 20260206) (generator "pcbnew") (layer "F.Cu") (attr through_hole)',
      f'(descr "AT8236 dual module carrier; female 2x7 sockets; row pitch from existing PCB, not module mechanical qualification")',
      f'(property "Reference" "REF**" (at {row/2} -5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
      f'(property "Value" {q(name)} (at {row/2} 19 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for side,dx in [(0,0),(1,row)]:
        for n in tree[1:]:
            if not isinstance(n,Node) or n[0] not in ['fp_line','fp_rect','fp_circle','fp_arc','pad','model']:continue
            c=capture_raw(serialize_with_quotes(n))
            if c[0]=='pad':
                k=int(c[1]);c[1]=capture_raw('(x '+q(k if side==0 else k+7)+')')[1]
            for key in ['start','end','center','mid','at']:
                for a in children(c,key):a[1]=capture_raw('(x '+num(float(a[1])+dx)+')')[1]
            if c[0]=='model':
                off=child(c,'offset');xyz=child(off,'xyz');xyz[1]=capture_raw('(x '+num(float(xyz[1])+dx)+')')[1]
            # Remove stock UUIDs so footprint editor allocates fresh ones.
            for n0 in list(c):
                if isinstance(n0,Node) and n0[0]=='uuid':c.remove(n0)
            body.append(serialize_with_quotes(c))
    left=['AOUT2','AOUT1','BIN1','BIN2','VCC','VM','GND']
    right=['GND','VM','VCC','AIN2','AIN1','BOUT1','BOUT2']
    for i in range(7):
        for dx,t in [(0,left[i]),(row,right[i])]:
            tx=dx+(3.2 if dx==0 else -3.2)
            body.append(f'(fp_text user {q(t)} (at {tx} {i*2.54} 0) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))')
    body += [f'(fp_text user "电容侧 / 模块顶部" (at {row/2} -2.8 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f'(fp_text user "排间距={row:.4f}毫米 / 请试装核验" (at {row/2} 17.4 0) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.12))))',')']
    path.write_text('\n'.join(body)+'\n',encoding='utf-8')
    return 'EdgeMind_Module:'+name

def rail_protection(p,x,y,source,target,ovtop,uvtop,ilim,fault):
    u=p.sym('EdgeMind_Power:TPS25940L',None,x,y,'TPS25940LRVCR',USBICFP,mpn='TPS25940LRVCR')
    vin=(x-27.94,u.pin(9)[1]);p.wire(vin,u.pin(9));p.label(source,vin,180)
    ci=C(p,x-27.94,y+2.54,'10uF 25V',fp=C8FP);p.wire(ci.pin(1),vin);p.dot(vin);p.ground(ci.pin(2))
    for k,xx,yy,top in [(14,x-63.5,y-2.54,uvtop),(15,x-46.99,y+20.32,ovtop)]:
        rt=R(p,xx,yy-10.16,top+' 0.1%');rb=R(p,xx,yy+10.16,'10.0k 0.1%');mid=(xx,yy)
        p.stub(rt,1,source,3.81);p.wire(rt.pin(2),mid,rb.pin(1));p.ground(rb.pin(2));p.dot(mid)
        if k==14:p.wire(mid,u.pin(k))
        else:p.wire(mid,(x-36.83,yy),(x-36.83,u.pin(k)[1]),u.pin(k))
    p.stub(u,1,'GND',3.81);p.stub(u,3,'GND',3.81);p.ground(u.pin(16))
    for k in [2,19]:p.nc(u,k)
    rl=R(p,x+40.64,y+22.86,ilim);cd=C(p,x+25.4,y+35.56,'4.7nF 50V')
    p.wire(u.pin(17),(rl.pin(1)[0],u.pin(17)[1]),rl.pin(1));p.ground(rl.pin(2))
    p.wire(u.pin(18),(cd.pin(1)[0],u.pin(18)[1]),cd.pin(1));p.ground(cd.pin(2))
    end=(x+64.77,u.pin(4)[1]);p.wire(u.pin(4),end);p.label(target,end)
    co=C(p,x+58.42,y+2.54,'4.7uF 10V',fp=C8FP);p.wire(co.pin(1),(co.pin(1)[0],end[1]));p.dot((co.pin(1)[0],end[1]));p.ground(co.pin(2))
    p.stub(u,20,fault,5.08)
    # Latched thermal fault reset, accessible without a GPIO tied to a powered divider.
    j=hdr(p,x-46.99,y+48.26,2,None,'SERVICE RESET: short EN to GND')
    p.wire(j.pin(1),(x-72.39,j.pin(1)[1]),(x-72.39,u.pin(14)[1]),(x-63.5,u.pin(14)[1]));p.dot((x-63.5,u.pin(14)[1]));p.ground(j.pin(2))
    return u

def build():
    assert hashlib.sha256((ROOT/(STEM+'.kicad_pcb')).read_bytes()).hexdigest()==EXPECTED_BOARD, 'PCB changed since start; re-read row pitch before rebuilding'
    root=Schematic(STEM+'.kicad_sch','EdgeMind Robot - power and AT8236 carrier',1,'A2')
    power=Schematic('01_power_input.kicad_sch','3S input protection and battery monitoring',2)
    usb=Schematic('02_usb_5v.kicad_sch','Two independent 5V USB-C sources',3)
    aux=Schematic('03_aux_3v3.kicad_sch','3.3V auxiliary and sensor power',4)
    safe=Schematic('04_motor_safety.kicad_sch','E-stop, explicit arm and fault latch',5)
    ml=Schematic('05_motor_left.kicad_sch','Left AT8236 module and motor power',6)
    mr=Schematic('06_motor_right.kicad_sch','Right AT8236 module and motor power',7)
    dump=Schematic('07_motor_dump.kicad_sch','Motor regeneration dump',8)
    prot=Schematic('08_rail_protection.kicad_sch','5V and 3.3V output protection',9)
    io=Schematic('09_control_io.kicad_sch','FPGA control and power monitoring interfaces',10)
    pages=[power,usb,aux,safe,ml,mr,dump,prot,io]
    root.text('保留两路 5V；新增 3.3V；两块 AT8236 双路模块各使用 A 通道。',25,30,2.0)
    root.text('区内实线连接；跨功能页使用全局网络标签。原 PCB 不同步更新。',25,41,1.5)
    root.text('3S INPUT / 9-12.6V\nProtected battery / external 3S BMS required\nF1 + reverse protection -> VBAT_SYS\nLogic: VLOGIC_IN -> 5V_FPGA / 5V_AI / 3V3\nMotors: independent switched VM_L and VM_R',25,62,1.4)
    for i,page in enumerate(pages):
        xx=25+(i%3)*123;yy=120+(i//3)*75
        root.items.append(f'(sheet (at {xx} {yy}) (size 110 40) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet:"+page.file))}) (property "Sheetname" {q(page.title)} (at {xx} {yy-1.27} 0) {effects(1.0,justify="left")}) (property "Sheetfile" {q(page.file)} (at {xx} {yy+42} 0) {effects(1.0,justify="left")}) (instances (project {q(STEM)} (path {q('/'+ROOT_ID)} (page {q(page.index)})))))')
    root.text('未纳入本次：PCB布线、步进驱动、FPGA RTL。\n定板前核对Rsense/VREF、编码器线序和ACG720供电口。\nAT8236排母保持原板排距；纠正对排引脚次序。',25,336,1.35)

    # 01 input: fuse followed by a P-FET connected in reverse-source orientation.
    p=power;p.box(15,15,380,89,'INPUT: fused 3S battery / reverse polarity / transient suppression')
    con=hdr(p,30,57.15,2,'CN1','XT60PW-M / 3S', 'Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal',a=180)
    p.ground(con.pin(1));p.flag('GND',(con.pin(1)[0],con.pin(1)[1]+3.81))
    f=p.sym('Device:Fuse','F1',76.2,con.pin(2)[1],'10A automotive fuse (initial)', 'Fuse:Fuse_Blade_ATO_directSolder',angle=90)
    p.wire(con.pin(2),f.pin(1))
    qrev=p.sym('Transistor_FET:Q_PMOS_GDS','Q1',111.76,68.58,'IRF4905',TO220,mpn='IRF4905',angle=90)
    p.wire(f.pin(2),(96.52,f.pin(2)[1]),(96.52,qrev.pin(2)[1]),qrev.pin(2))
    end=(187.96,qrev.pin(3)[1]);p.wire(qrev.pin(3),end);p.flag('VBAT_SYS',end)
    rg=R(p,111.76,83.82,'100k');p.wire(qrev.pin(1),rg.pin(1));p.ground(rg.pin(2))
    dz=p.sym('Device:D_Zener',None,134.62,78.74,'BZT52C12', 'Diode_SMD:D_SOD-123',angle=270)
    p.wire(dz.pin(1),(134.62,end[1]));p.dot((134.62,end[1]));p.wire(dz.pin(2),(124.46,dz.pin(2)[1]),(124.46,76.2),(111.76,76.2));p.dot((111.76,76.2))
    p.wire(end,(end[0],55.88),(269.24,55.88))
    cap(p,205.74,66.04,'VBAT_SYS','470uF 35V low-ESR',ref='C58',polar=True,bus=(205.74,55.88))
    cap(p,226.06,66.04,'VBAT_SYS','10uF 50V',ref='C59',bus=(226.06,55.88))
    cap(p,246.38,66.04,'VBAT_SYS','100nF 50V',ref='C60',bus=(246.38,55.88))
    tv=p.sym('Device:D_TVS','D1',269.24,66.04,'SMBJ15CA','Diode_SMD:D_SMB',angle=270,mpn='SMBJ15CA')
    p.wire(tv.pin(1),(269.24,55.88));p.ground(tv.pin(2))
    p.text('TVS does not clamp VM below 17V.\nOV cutoff and motor dump paths are separate.\nQ1: D=input, S=protected output;\nregeneration can return to a connected battery.',293,53,1.0)
    p.box(15,113,191,146,'LOGIC INPUT: 4.48A bus limit / UV off ~9.01V / OV ~14.04V')
    e_fuse(p,99.06,164,'VLOGIC_IN',ref='U6',limit='4.02k',uvtop='70.3k',enable='VREF_2V495')
    # Stable 2.495V raw-bus shunt reference enables the logic eFuse independently of 3V3.
    tl=p.sym('Reference_Voltage:TL431DBZ',None,276.86,126.99,'TL431BIDBZR','Package_TO_SOT_SMD:SOT-23',angle=90,mpn='TL431BIDBZR')
    p.wire(tl.pin(2), (tl.pin(2)[0],tl.pin(1)[1]),tl.pin(1));p.ground(tl.pin(3))
    bias=R(p,276.86,109.22,'2.2k');p.stub(bias,1,'VBAT_SYS',3.81);p.wire(bias.pin(2),tl.pin(1));p.dot(tl.pin(1));p.label('VREF_2V495',tl.pin(1))
    # Use only one name for this local reference in final netlist; enable wire labels merge intentionally.
    cap(p,176.53,233.68,'VLOGIC_IN','100uF 25V',polar=True)
    tp(p,190.5,219.71,'VLOGIC_IN')
    p.text('External protected 3S pack/BMS is required.\nThis board does not charge or balance cells.\nLogic remains alive after motor E-stop.\nTotal-voltage monitoring cannot detect an imbalanced cell.',223.52,236.22,1.1)
    p.box(219.71,143.51,175,78,'BATTERY WARNING + analog voltage measurement')
    cmp=p.sym('Comparator:LM393',None,312.42,175.26,'LM393BIDR',SO8,mpn='LM393BIDR',unit=1)
    top=R(p,246.38,160.02,'30.9k 0.1%');bottom=R(p,246.38,185.42,'10.0k 0.1%');mid=(246.38,172.72)
    p.stub(top,1,'VBAT_SYS',3.81);p.wire(top.pin(2),mid,bottom.pin(1));p.ground(bottom.pin(2));p.wire(mid,cmp.pin(3));p.dot(mid)
    p.stub(cmp,2,'VREF_2V495',7.62);p.stub(cmp,1,'BAT_WARN_N',7.62);pull(p,345.44,160.02,'BAT_WARN_N')
    rhi=R(p,292.1,198.12,'1M',a=90);p.wire(rhi.pin(1),(246.38,198.12),bottom.pin(1));p.dot(bottom.pin(1));p.wire(rhi.pin(2),(337.82,198.12),(337.82,175.26),cmp.pin(1));p.dot((337.82,175.26))
    cp=p.sym('Comparator:LM393',cmp.ref,368.3,203.2,'LM393BIDR',SO8,mpn='LM393BIDR',unit=3)
    p.stub(cp,8,'VBAT_SYS',3.81);p.ground(cp.pin(4));decouple(p,384.81,203.2,'VBAT_SYS')
    cu=p.sym('Comparator:LM393',cmp.ref,312.42,210.82,'LM393BIDR',SO8,mpn='LM393BIDR',unit=2)
    p.stub(cu,5,'GND',3.81);p.stub(cu,6,'VREF_2V495',3.81);p.nc(cu,7)
    # BAT_ADC: 100k / 27.4k, 12.6V -> 2.71V; ADC is external.
    ra=R(p,368.3,110.49,'100k 0.1%');rb=R(p,368.3,129.54,'27.4k 0.1%');p.stub(ra,1,'VBAT_SYS',3.81)
    p.wire(ra.pin(2),rb.pin(1));am=(368.3,120.015);p.label('BAT_ADC',am);p.dot(am);p.ground(rb.pin(2))
    ca=C(p,389.89,129.54,'100nF 25V');p.wire(ca.pin(1),(389.89,120.015),am);p.ground(ca.pin(2))

    # 02 retain both independent MP2236 rails and connect complete Type-C source controllers.
    buck5(usb,78.74,'U5','L1',['C1','C2','C3'],['C4','C5'],'R1','C6','C11','R2','R3','C7','+5V_FPGA','USB1','U7')
    buck5(usb,207.01,'U1','L2',['C8','C9','C10'],['C12','C13'],'R6','C14','C16','R11','R12','C15','+5V_AI','USB2','U8')
    usb.text('两路输出不并联。Buck设为5.155V补偿开关压降；端口与板端电压须实测。',18,280,1.15)

    # 03 independent 3.3V buck, split local logic/encoder and filtered sensor supply.
    p=aux;p.box(15,15,218,135,'ADDED: independent 3.3V buck / initial system budget 0.5A')
    u=p.sym('Regulator_Switching:AP63203WU','U3',93.98,68.58,'AP63203WU-7','Package_TO_SOT_SMD:TSOT-23-6',mpn='AP63203WU-7')
    v=(45.72,u.pin(3)[1]);p.wire(v,u.pin(3));p.label('VLOGIC_IN',v,180)
    ci=C(p,45.72,81.28,'10uF 25V',fp=C8FP);p.wire(ci.pin(1),v);p.dot(v);p.ground(ci.pin(2))
    p.wire(u.pin(2),(73.66,u.pin(2)[1]),(73.66,v[1]));p.dot((73.66,v[1]));p.ground(u.pin(4))
    ll=p.sym('Device:L','L3',146.05,u.pin(5)[1],'4.7uH XAL7030-472',IND,angle=90,mpn='XAL7030-472MEC');p.wire(u.pin(5),ll.pin(1))
    out=(207.01,ll.pin(2)[1]);p.wire(ll.pin(2),out);p.flag('+3V3_RAW',out)
    bs=C(p,124.46,86.36,'100nF 50V');p.wire(u.pin(6),(116.84,u.pin(6)[1]),(116.84,bs.pin(2)[1]),bs.pin(2));p.wire(bs.pin(1),(124.46,u.pin(5)[1]));p.dot((124.46,u.pin(5)[1]))
    for xx in [177.8,196.85]:
        co=C(p,xx,90.17,'22uF 10V X7R',fp=C8FP);p.wire(co.pin(1),(xx,out[1]));p.dot((xx,out[1]));p.ground(co.pin(2))
    p.wire(u.pin(1),(161.29,u.pin(1)[1]),(161.29,out[1]));p.dot((161.29,out[1]))
    tp(p,207.01,107.95,'+3V3')
    p.text('FB senses 3V3_RAW before output eFuse.\nAP63203 2A; output eFuse ~1A; budget 0.5A.\n4.7uH is within datasheet 2.2-10uH range.\nFPGA 3.3V is not hard-paralleled.',25,120,1.05)
    p.box(245,15,149,135,'SENSOR FILTER + 3V3 OUTPUT')
    bead=p.sym('Device:FerriteBead',None,279.4,53.34,'BLM21PG221SN1D','Inductor_SMD:L_0805_2012Metric',angle=90,mpn='BLM21PG221SN1D')
    p.stub(bead,1,'+3V3',5.08);p.stub(bead,2,'+3V3_SENS',5.08)
    cap(p,308.61,78.74,'+3V3_SENS','10uF 10V X7R');decouple(p,330.2,78.74,'+3V3_SENS')
    hdr(p,365.76,119.38,2,None,'3V3 AUX OUT',TERM,nets=['+3V3_SENS','GND'])
    for i,name in enumerate(['IMU PWR','TOF1 PWR','TOF2 PWR','TOF3 PWR']):
        xx=63.5+(i%2)*160;yy=192.5+(i//2)*49
        h=hdr(p,xx,yy,2,None,name,'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',nets=['+3V3_SENS','GND'])
        decouple(p,xx+35.56,yy,'+3V3_SENS')
    p.text('Power-only headers. Sensor signals connect to FPGA.\nVerify each finished module accepts 3.3V; bare VL53L1X AVDD is a separate design.\nEncoder supply uses +3V3; no connection to FPGA onboard regulator output.',18,275,1.1)

    # 04 Safety: E-stop NC return is pulled down; arm needs a rising edge.
    # Delayed Q masks shutdown/startup FLT state without preventing re-arm.
    p=safe;p.box(15,15,379,250,'MOTOR SAFETY: power-on disarmed / physical NC E-stop / explicit arm edge')
    estop=hdr(p,50.8,57.15,2,None,'ESTOP NC LOOP',TERM,nets=['+3V3','ESTOP_OK'])
    down(p,86.36,62.23,'ESTOP_OK');down(p,48.26,101.6,'MOTOR_PERMIT');down(p,81.28,101.6,'MOTOR_ARM')
    pull(p,114.3,45.72,'EXT_KILL_N')
    rst=p.sym('Power_Supervisor:MCP100-300D',None,162.56,68.58,'MCP100-300DI/TO','Package_TO_SOT_THT:TO-92_Inline',mpn='MCP100-300DI/TO')
    p.stub(rst,2,'+3V3',3.81);p.ground(rst.pin(3));p.stub(rst,1,'POR_OK',5.08);decouple(p,180.34,90.17)
    def gate(name,x,y,a,b,out,ref=None):
        g=p.sym('74xGxx:'+name,ref,x,y,'SN'+name+'DBVR',SOT5,mpn='SN'+name+'DBVR')
        p.stub(g,1,a,5.08);p.stub(g,2,b,5.08);p.stub(g,4,out,5.08);p.stub(g,5,'+3V3',3.81);p.ground(g.pin(3));decouple(p,x+21.59,y+22.86)
        return g
    gate('74LVC1G08',241.3,62.23,'ESTOP_OK','MOTOR_PERMIT','PERMIT_OK')
    gate('74LVC1G08',327.66,62.23,'POR_OK','EXT_KILL_N','RESET_OK')
    gate('74LVC1G08',241.3,119.38,'PERMIT_OK','RESET_OK','MANUAL_OK')
    gate('74LVC1G08',327.66,119.38,'MANUAL_OK','EFUSE_OK_MASKED','ARM_CLEAR_N')
    ff=p.sym('74xx:74HC74',None,139.7,153.67,'SN74HC74DR',SO14,unit=1,mpn='SN74HC74DR')
    p.stub(ff,2,'+3V3',5.08);p.stub(ff,3,'MOTOR_ARM',7.62);p.stub(ff,4,'+3V3',3.81);p.stub(ff,1,'ARM_CLEAR_N',7.62);p.stub(ff,5,'MOTOR_ARMED',7.62);p.nc(ff,6)
    ffu=p.sym('74xx:74HC74',ff.ref,56.515,153.67,'SN74HC74DR',SO14,unit=2,mpn='SN74HC74DR')
    for k in [11,12,13]:p.stub(ffu,k,'GND',3.81)
    p.stub(ffu,10,'+3V3',3.81);p.nc(ffu,8);p.nc(ffu,9)
    ffp=p.sym('74xx:74HC74',ff.ref,195.58,153.67,'SN74HC74DR',SO14,unit=3,mpn='SN74HC74DR');p.stub(ffp,14,'+3V3',3.81);p.ground(ffp.pin(7));decouple(p,212.09,163.83)
    mask=gate('74LVC1G08',241.3,202.565,'VM_L_FLT_N','VM_R_FLT_N','EFUSE_OK')
    gm=gate('74LVC1G32',327.66,202.565,'EFUSE_OK','ARM_DELAY_N','EFUSE_OK_MASKED')
    rt=R(p,50.8,217.17,'100k',a=90);ct=C(p,78.74,232.41,'1uF 25V');p.stub(rt,1,'MOTOR_ARMED',5.08);p.wire(rt.pin(2),(78.74,217.17),ct.pin(1));p.ground(ct.pin(2));p.dot((78.74,217.17))
    inv=p.sym('74xGxx:74LVC1G14',None,144.78,217.17,'SN74LVC1G14DBVR',SOT5,mpn='SN74LVC1G14DBVR');p.wire((78.74,217.17),inv.pin(2));p.nc(inv,1);p.stub(inv,4,'ARM_DELAY_N',5.08);p.stub(inv,5,'+3V3',3.81);p.ground(inv.pin(3));decouple(p,167.64,240.03)
    # Explicit SHDN down resistor defeats the eFuse's internal enable pullup when 3V3 is absent.
    down(p,195.58,226.06,'MOTOR_ARMED','4.7k')
    p.text('ESTOP / PERMIT / KILL / POR clear immediately.\nRestore does not arm; pulse MOTOR_ARM.\nFPGA drops PERMIT on reset/stall/timeout.\nStartup FLT mask: RC ~0.1s; bench-verify.',18,119.38,1.1)

    # 05 motor power, adjustable reference, hardware-gated inputs and local energy storage.
    for p,side,base,modref,row,jref,label in [(ml,'L',25.4,'U2',23.0005,'J3','LEFT'),(mr,'R',25.4,'U4',23.1275,'J4','RIGHT')]:
        p.paper='A2'
        cx=base+95
        p.box(base,15,270,372,label+' MOTOR: protected VM / A-channel AT8236 / female sockets')
        uef=e_fuse(p,cx,71.12,'VM_'+side,limit='7.15k',uvtop='75.0k')
        cap(p,base+223.52,68.58,'VM_'+side,'470uF 25V low-ESR',polar=True)
        decouple(p,base+244.475,68.58,'VM_'+side)
        tp(p,base+223.52,104.14,'VM_'+side)
        at=p.sym('EdgeMind_Power:AT8236_Dual_Module',modref,base+154.94,228.6,'AT8236 dual module',module_fp(row),mpn='AT8236 dual module / vendor-specific')
        # Main local supply is wired directly down from the eFuse output.
        p.wire(uef.pin(17),(base+190.5,uef.pin(17)[1]),(base+190.5,198.12),(at.pin(6)[0],198.12),at.pin(6));p.dot((base+190.5,uef.pin(17)[1]));p.ground(at.pin(7))
        # VREF potentiometer, fail-safe wiper pulldown; range 0..3.3V. Calibrate before fitting motor.
        rv=p.sym('Device:R_Potentiometer',None,base+102.87,163.83,'10k 3296W / VREF trim','Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical',mpn='3296W-1-103LF')
        p.stub(rv,1,'+3V3_SENS',3.81);p.ground(rv.pin(3));rseries=R(p,base+125.73,163.83,'1k',a=90)
        p.wire(rv.pin(2),rseries.pin(1));rpd=R(p,base+146.05,183.515,'100k');cref=C(p,base+168.275,183.515,'1uF 25V')
        vref=(base+146.05,163.83);p.wire(rseries.pin(2),vref,(at.pin(5)[0],163.83),at.pin(5));p.wire(vref,rpd.pin(1));p.dot(vref);p.ground(rpd.pin(2));p.wire(cref.pin(1),(cref.pin(1)[0],163.83),vref);p.ground(cref.pin(2));p.dot((at.pin(5)[0],163.83));p.label('VREF_'+side,vref)
        tp(p,base+207.01,183.515,'VREF_'+side)
        # Each PWM path ANDs with the hardware arm latch, preserving fast-decay IN1/IN2 control.
        for i,k in enumerate([12,11]):
            gy=at.pin(k)[1] if i==0 else at.pin(k)[1]+27.94
            g=p.sym('74xGxx:74LVC1G08',None,base+76.2,gy,'SN74LVC1G08DBVR',SOT5,mpn='SN74LVC1G08DBVR')
            p.stub(g,1,side+'_PWM_'+('FWD_RAW' if i==0 else 'REV_RAW'),5.08);p.stub(g,2,'MOTOR_ARMED',5.08);p.stub(g,5,'+3V3',3.81);p.ground(g.pin(3));decouple(p,base+50.8,gy+20.32)
            if i==0:p.wire(g.pin(4),at.pin(k))
            else:p.wire(g.pin(4),(base+114.3,gy),(base+114.3,at.pin(k)[1]),at.pin(k))
            rd=R(p,base+122 if i==0 else base+128,gy+10.16,'10k')
            p.wire(rd.pin(1),(rd.pin(1)[0],at.pin(k)[1]));p.dot((rd.pin(1)[0],at.pin(k)[1]));p.ground(rd.pin(2))
        p.wire(at.pin(3),(base+134.62,at.pin(3)[1]),(base+134.62,at.pin(4)[1]),at.pin(4));p.ground((base+134.62,at.pin(4)[1]));p.dot((base+134.62,at.pin(4)[1]))
        p.nc(at,13);p.nc(at,14)
        mot=hdr(p,base+232.41,228.6,6,jref,label+' MG513 (verify harness)','Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical')
        p.wire(at.pin(1),(base+198.12,at.pin(1)[1]),(base+198.12,mot.pin(1)[1]),mot.pin(1))
        p.wire(at.pin(2),(base+190.5,at.pin(2)[1]),(base+190.5,mot.pin(6)[1]),mot.pin(6))
        for k,net in [(2,'+3V3'),(3,'ENC_'+side+'_A'),(4,'ENC_'+side+'_B'),(5,'GND')]:p.stub(mot,k,net,5.08)
        decouple(p,base+237.49,264.16,'+3V3')
        # Encoder RC filtering: 100R / 1nF plus weak pulls; verify highest PPR waveform.
        for i,ch in enumerate(['A','B']):
            yy=308.61+i*27.94;renc=R(p,base+160.02,yy,'100R',a=90);p.stub(renc,1,'ENC_'+side+'_'+ch,5.08)
            target=(base+187.96,yy);p.wire(renc.pin(2),target);p.label('ENC_'+side+'_'+ch+'_FPGA',target)
            cc=C(p,base+180.34,yy+10.16,'1nF C0G');p.wire(cc.pin(1),(180.34+base,yy));p.dot((180.34+base,yy));p.ground(cc.pin(2))
            rp=R(p,base+219.71,yy-7.62,'10k');p.stub(rp,1,'+3V3',3.81);p.wire(rp.pin(2),(base+219.71,yy),target);p.dot(target)
        p.text(f'ROW PITCH: {row:.4f}mm from existing PCB\nItrip = VREF / (10 x Rsense). Measure module Rsense first.\nVREF <0.5V is not specified for accurate current regulation.\nVM bus eFuse ~2.52A is not winding-current regulation.\nB inputs tied low; B outputs unused. PWM: 10=FWD, 01=REV, 00=OFF.',base+8,365,1.0)

    # Global hardware interfaces retain original J1/J2 encoder/control ordering where possible.
    p=io
    p.box(15,15,380,228,'FPGA control / power monitoring / no regulator paralleling')
    hdr(p,160.02,62.23,8,'J1','LEFT CTRL',nets=['L_PWM_FWD_RAW','L_PWM_REV_RAW','MOTOR_ARM','MOTOR_PERMIT','GND',None,'ENC_L_A_FPGA','ENC_L_B_FPGA'])
    hdr(p,345.44,62.23,8,'J2','RIGHT CTRL',nets=['ENC_R_B_FPGA','ENC_R_A_FPGA',None,'GND','R_PWM_FWD_RAW','R_PWM_REV_RAW','EXT_KILL_N','MOTOR_ARMED'])
    hdr(p,160.02,175.26,12,None,'POWER MONITOR / external ADC',nets=['+3V3','GND','BAT_ADC','BAT_WARN_N','VM_L_IMON','VM_R_IMON','VLOGIC_IN_IMON','VM_L_FLT_N','VM_R_FLT_N','USB1_FLT_N','USB2_FLT_N','ESTOP_OK'])
    p.text('J1.6 and J2.3 intentionally NC.\nDo not join onboard 3.3V regulators.\nControl IO: FPGA 3.3V domain.\nIMON / BAT_ADC require external ADC.\nLichee Pi GPIO needs level translation.\nPERMIT: hold low through configuration.\nARM: explicit rising edge after checks.\nKILL_N: external open-drain fault input.',224.79,154.94,1.15)

    # Regenerative overvoltage dump. An external chassis resistor is mandatory when
    # the battery/bench supply cannot absorb returned energy; no guessed onboard 100W footprint.
    p=dump
    p.box(15,15,380,211,'REGEN DUMP: two external 3.3R >=100W resistors')
    brref=None
    for i,side in enumerate(['L','R']):
        yy=63.5+i*78.74
        cx=180.34
        cmp=p.sym('Comparator:LM393',brref,cx,yy,'LM393BIDR',SO8,unit=i+1,mpn='LM393BIDR');brref=cmp.ref
        cp,cn,co=(3,2,1) if i==0 else (5,6,7)
        top=R(p,125.73,yy-13.97,'51.1k 0.1%');bt=R(p,125.73,yy+11.43,'10.0k 0.1%');m=(125.73,yy-2.54)
        p.stub(top,1,'VM_'+side,3.81);p.wire(top.pin(2),m,bt.pin(1));p.ground(bt.pin(2));p.wire(m,cmp.pin(cp));p.dot(m)
        p.stub(cmp,cn,'VREF_2V495',5.08)
        gate=(211.455,yy);p.wire(cmp.pin(co),gate)
        rg=R(p,211.455,yy-14.605,'4.7k');p.stub(rg,1,'VM_'+side,3.81);p.wire(rg.pin(2),gate);p.dot(gate)
        mos=p.sym('Transistor_FET:Q_NMOS_GDS',None,242.57,yy,'IRLZ44N',TO220,mpn='IRLZ44N')
        p.wire(gate,mos.pin(1));p.ground(mos.pin(3))
        z=p.sym('Device:D_Zener',None,226.06,yy+15.24,'BZT52C12','Diode_SMD:D_SOD-123',angle=270);p.wire(z.pin(1),(226.06,yy));p.dot((226.06,yy));p.ground(z.pin(2))
        rh=R(p,161.29,yy+25.4,'1M',a=90);p.wire(rh.pin(1),(125.73,yy+25.4),bt.pin(1));p.dot(bt.pin(1));p.wire(rh.pin(2),(199.39,yy+25.4),(199.39,yy),gate);p.dot((199.39,yy))
        conn=hdr(p,350.52,yy-15.24,2,None,side+' DUMP resistor',TERM)
        p.stub(conn,1,'VM_'+side,5.08);p.wire(conn.pin(2),(mos.pin(2)[0],conn.pin(2)[1]),mos.pin(2))
    pp=p.sym('Comparator:LM393',brref,264.795,196.85,'LM393BIDR',SO8,unit=3,mpn='LM393BIDR');p.stub(pp,8,'VBAT_SYS',3.81);p.ground(pp.pin(4));decouple(p,292.735,196.85,'VBAT_SYS')
    p.text('Dump ON ~15.39V / OFF ~14.6V: bench-verify overshoot.\nExternal resistors: 3.3R >=100W each, mounted on chassis.\nAbout 72W per resistor at 15.4V while conducting.\nPowered from raw bus; works while 3V3 protection is off.\nConnect dump when supply/BMS cannot absorb regeneration.',18,240.03,1.1)
    p=prot
    p.box(15,15,192,123,'5V FPGA / UV ~4.60V / OV ~5.366V')
    p.box(218,15,181,123,'5V AI / UV ~4.60V / OV ~5.366V')
    p.box(15,150,192,123,'3V3 / UV ~2.97V / OV ~3.515V')
    rail_protection(p,99.06,63.5,'+5V_FPGA','+5V_FPGA_PROT','44.2k','36.5k','22.1k','USB1_FLT_N')
    rail_protection(p,302.26,63.5,'+5V_AI','+5V_AI_PROT','44.2k','36.5k','22.1k','USB2_FLT_N')
    rail_protection(p,99.06,198.12,'+3V3_RAW','+3V3','25.5k','20.0k','88.7k','AUX_FLT_N')
    pull(p,243.84,166.37,'AUX_FLT_N')
    hdr(p,347.98,195.58,2,None,'AUX STATUS',nets=['AUX_FLT_N','GND'])
    p.text('TPS25940L: true reverse-current blocking.\n5V current limit ~4.03A, above USB switch limit.\n3V3 current limit ~0.99A, budget 0.5A.\nOV cutoff worst-case nominal thresholds\nincluding tolerance remain below 5.5V / 3.6V.\nThermal latch reset: momentarily short\nservice header after fault removal.\nVerify OV response and overshoot on bench.',219.71,231.14,1.0)
    for page in [root]+pages:page.finish()
    # Project-local symbols only for devices absent from stock, not custom physical packages.
    local=['(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor")']+list(CUSTOM.values())+[')']
    (ROOT/'EdgeMind_Power.kicad_sym').write_text('\n'.join(local)+'\n',encoding='utf-8')
    for file,key,name,uri in [('sym-lib-table','sym_lib_table','EdgeMind_Power','EdgeMind_Power.kicad_sym'),('fp-lib-table','fp_lib_table','EdgeMind_Module','EdgeMind_Module.pretty')]:
        path=ROOT/file;txt=path.read_text(encoding='utf-8')
        if f'(name "{name}")' not in txt:
            txt=txt.rstrip()[:-1]+f'\n (lib (name "{name}") (type "KiCad") (uri "${{KIPRJMOD}}/{uri}") (options "") (descr "Schematic redesign R2"))\n)\n'
            path.write_text(txt,encoding='utf-8')
    assert hashlib.sha256((ROOT/(STEM+'.kicad_pcb')).read_bytes()).hexdigest()==EXPECTED_BOARD
    (ROOT/'review'/'redesign-components.json').write_text(json.dumps(COMPONENTS,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Generated',len(pages)+1,'sheets,',len([c for c in COMPONENTS if not c['reference'].startswith('#')]),'symbol instances; PCB unchanged')

if __name__=='__main__':
    raise SystemExit('Use redesign_budget.py for the current independently powered 3V3 / 6P USB-C design.')
