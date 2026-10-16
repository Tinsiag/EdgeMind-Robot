"""Assemble the R3X running gear, SolidCraft base and existing EdgeMind boards.

Run with the FreeCAD Python runtime after extract_reference.py and
solidcraft_workflow.py. All new deliverables stay in this v2 directory.
"""
from pathlib import Path
import json,math,zipfile,hashlib
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part,MeshPart

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
P=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
REF=json.loads((HERE/'reference-extraction.json').read_text(encoding='utf-8'))
V=App.Vector
LOW=P['lower_deck_bottom_z'];TOP=P['upper_deck_bottom_z']
LT=P['lower_plate_thickness'];UT=P['upper_plate_thickness']
DZ=LOW-18
old_report=json.loads((HERE.parent/'v1-fixed-front-wheels/verification.json').read_text(encoding='utf-8'))
old_solids=Part.read(str(HERE.parent/'v1-fixed-front-wheels/EdgeMind_Assembly.step')).Solids
assert len(old_solids)==len(old_report['parts'])
old_shapes={p['name']:s for p,s in zip(old_report['parts'],old_solids)}
doc=App.newDocument('EdgeMindR3XChassis')
groups={}
for name,label in [('Shell','01 下层外壳'),('Mounts','02 支撑与安装件'),('Wheels','03 万向轮与后驱动轮'),('Hardware','04 电机和电源板'),('Fasteners','05 紧固件参考')]:
    g=doc.addObject('App::DocumentObjectGroup',name);g.Label=label;groups[name]=g
upper=doc.addObject('App::Part','UpperAssembly');upper.Label='06 上层总成（修改 Placement Z 可整体展开）'
items=[]
colors={'shell':(.1,.13,.16),'silver':(.62,.67,.72),'gold':(.86,.57,.13),'rubber':(.1,.105,.115),'board':(.04,.32,.55),'hub':(.24,.27,.30)}
def log(s):print(s,flush=True)
def bounds(s):
    b=s.optimalBoundingBox(False,False)
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def box(x,y,z,dx,dy,dz):return Part.makeBox(dx,dy,dz,V(x,y,z))
def cyl(r,h,p):return Part.makeCylinder(r,h,V(*p))
def ring(ro,ri,h,p):return cyl(ro,h,p).cut(cyl(ri,h,p))
def polygon(xy,z,h):
    pts=[V(x,y,z) for x,y in xy]
    return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,h))
def cut(s,tools):return s.cut(Part.makeCompound(tools)).removeSplitter() if tools else s
def add(name,label,s,color='shell',category='Shell',role='designed',export=False,is_upper=False,known=None):
    assert not s.isNull() and s.Solids,name
    valid=known['valid'] if known else s.isValid()
    volume=known['volume_mm3'] if known else s.Volume
    assert valid and volume>0,name
    o=doc.addObject('Part::Feature',name);o.Label=label;o.Shape=s
    o.addProperty('App::PropertyString','DesignRole','Design').DesignRole=role
    o.addProperty('App::PropertyString','DimensionUnit','Design').DimensionUnit='mm'
    if is_upper:upper.addObject(o)
    else:groups[category].addObject(o)
    rgb=colors[color] if isinstance(color,str) else color
    items.append({'name':name,'label':label,'object':o,'category':category,'role':role,'color':rgb,
                  'export_part':export,'upper_assembly':is_upper,'valid':valid,'volume_mm3':volume,
                  'bounds':bounds(s)})
    return o

log('Read and independently compare SolidCraft base with exact requested cuts')
base=Part.read(str(HERE/'SolidCraft_LowerDeck.step'))
profile=[(-70,-130),(70,-130),(90,-110),(90,118),(78,130),(-78,130),(-90,118),(-90,-110)]
expected=polygon(profile,LOW,LT)
holes=[(x,y,1.7) for x,y,r in REF['rear_bracket_mount_holes_xy_radius']]
holes += [(x,y,1.7) for x in (-76,76) for y in (-111,114)]
caster_holes=[(sx*P['caster_pivot_x']+dx,P['caster_pivot_y']+dy,1.7) for sx in (-1,1) for dx in (-15,15) for dy in (-12,12)]
holes += caster_holes
power_holes=[(x-49.992,y+P['power_board_centre_y']+25,1.7) for x,y,r in old_report['power_pcb_holes_from_step']]
holes += power_holes
tools=[cyl(r,LT+2,(x,y,LOW-1)) for x,y,r in holes]
pw=P['battery_width']+2*P['battery_clearance_each_side'];pl=P['battery_length']+2*P['battery_clearance_each_side']
for sx in (-1,1):
    for yy in P['tie_slot_y']:
        tools.append(box(sx*P['tie_slot_x']-P['tie_slot_width']/2,yy-P['tie_slot_length']/2,LOW-1,P['tie_slot_width'],P['tie_slot_length'],LT+2))
expected=cut(expected,tools)
gw=P['battery_guard_wall'];gh=P['battery_guard_height'];by=P['battery_centre_y']
fence=box(-pw/2-gw,by-pl/2-gw,LOW+LT-.5,pw+2*gw,pl+2*gw,gh+.5).cut(box(-pw/2,by-pl/2,LOW+LT-.6,pw,pl,gh+.7))
expected=expected.fuse(fence).removeSplitter()
delta=base.cut(expected).Volume+expected.cut(base).Volume
assert delta<.05,('SolidCraft base mismatch',delta)
assert max(abs(a-b) for a,b in zip(bounds(base),bounds(expected)))<.005
add('LowerDeck','4mm平底板 / 电池围栏内腔87×49高3 / 四个扎带孔',base,export=True)

log('Retain upper boards, power-board geometry and shell proportions')
for item in old_report['parts']:
    name=item['name']
    is_up=name=='UpperDeck' or name.startswith(('BoardPost','FPGA','LPi4A','UpperScrew'))
    if not is_up and not name.startswith('PowerComponent'):continue
    s=old_shapes[name].copy()
    sb=bounds(s);rb=item['bounds']
    assert all(sb[k]>=rb[k]-.05 and sb[k+3]<=rb[k+3]+.05 for k in range(3)),('V1 reference mismatch',name,sb,rb)
    s.translate(V(0,0,DZ) if is_up else V(0,P['power_board_centre_y']+90,DZ+LT-3))
    color='board' if name in ('FPGAReference','LPi4AReference') else ('gold' if name.startswith('BoardPost') else 'silver')
    if name=='UpperDeck':color='shell'
    if name.startswith('FPGAChip') or name=='LPi4ACore':color='rubber'
    if name.startswith('PowerComponent'):
        b=s.BoundBox
        color='board' if b.XLength>95 and b.YLength>45 and b.ZLength<2 else ('hub' if b.ZLength<2 else 'silver')
    label='上层可拆托盘 / 与板卡一起整体展开' if name=='UpperDeck' else item['label']
    add(name,label,s,color,item['category'],item['role'],export=name=='UpperDeck',is_upper=is_up)

for side,suf in [(-1,'L'),(1,'R')]:
    panel=box(-90 if side<0 else 87,-105,LOW+LT,3,216,22)
    vents=[box(-91,yy,LOW+zz,182,ll,3.2) for yy,ll in [(-75,43),(-15,42),(37,22)] for zz in (10,18)]
    add('SidePanel'+suf,'通风侧板'+suf,cut(panel,vents),export=True)
    add('SideRail'+suf,'侧护边'+suf,box(-92.5 if side<0 else 90,-107,LOW+26,2.5,211,12),'silver',export=True)
    add('Accent'+suf,'侧边琥珀装饰条'+suf,box(-93.3 if side<0 else 92.5,-102,LOW+34,.8,201,2),'gold',role='decorative')
front=cut(box(-68,-130,LOW+LT,136,3,23),[box(-46,-131,LOW+z,92,5,3) for z in (9,16)])
add('FrontBumper','前通风护板',front,export=True)
for side,suf in [(-1,'L'),(1,'R')]:
    cheek=polygon([(side*68,-130),(side*70,-130),(side*90,-110),(side*88,-108)],LOW+LT,23)
    add('FrontCheek'+suf,'前倒角护板'+suf,cheek,export=True)
rear=cut(box(-75,127,LOW+LT,150,3,26),[box(-30,126,LOW+LT+8,60,5,10)])
add('RearBumper','后护板与线束出口',rear,export=True)
for i,(x,y) in enumerate([(x,y) for x in (-76,76) for y in (-111,114)],1):
    add('MainPost'+str(i),'上下层支柱'+str(i),ring(4.5,1.65,TOP-LOW-LT,(x,y,LOW+LT)),'gold','Mounts')
for i,(x,y,r) in enumerate(power_holes,1):
    add('PowerPost'+str(i),'原电源板安装支柱'+str(i),ring(3,1.6,8,(x,y,LOW+LT)),'gold','Mounts')

log('Install actual R3X motors, mounts, wheels, hubs and duplicated front caster')
for part in REF['parts']:
    name=part['name'];s=Part.Shape();s.read(str(HERE/'hardware-brep'/(name+'.brep')))
    color='rubber' if name.endswith('Wheel') else ('hub' if name.endswith('Hub') else 'silver')
    label={'MotorBracket':'R3X原配电机安装支架','Motor':'R3X原电机零件','Rear':'R3X原后轮/轮毂','Caster':'R3X前万向轮'}
    prefix=next(p for p in label if name.startswith(p))
    add(name,label[prefix]+' '+name,s,color,part['category'],'source_geometry',known=part)
for i,(x,y,r) in enumerate(caster_holes,1):
    add('CasterSpacer'+str(i),'万向轮安装隔柱 '+str(i)+' / 23.781mm',ring(3,1.65,P['caster_spacer_length'],(x,y,P['caster_top_z'])),'gold','Mounts',export=i==1)
    bolt=cyl(1.5,LT+P['caster_spacer_length']+3,(x,y,P['caster_top_z']-3)).fuse(cyl(2.8,1.8,(x,y,LOW+LT)))
    add('CasterBolt'+str(i),'万向轮M3长螺钉示意'+str(i),bolt,'silver','Fasteners','fastener_reference')

doc.recompute()
log('Check shell clearances and caster sweep')
collisions=[]
targets=[i for i in items if i['role']=='source_geometry' or i['name'].startswith(('FPGA','LPi4A'))]
designed=[i for i in items if i['category'] in ('Shell','Mounts') and i['role']=='designed']
for a in designed:
    for b in targets:
        sa,sb=a['object'].Shape,b['object'].Shape
        if not sa.BoundBox.intersect(sb.BoundBox):continue
        vol=sa.common(sb).Volume
        if vol>.02:collisions.append({'a':a['name'],'b':b['name'],'volume_mm3':vol})
wheel_ground=[next(i for i in items if i['name']==name)['bounds'][2] for name in ['RearLWheel','RearRWheel','CasterLWheel','CasterRWheel']]
assert max(abs(z) for z in wheel_ground)<.001,wheel_ground
all_bounds=[i['bounds'] for i in items]
overall=[min(b[k] for b in all_bounds) for k in range(3)]+[max(b[k] for b in all_bounds) for k in range(3,6)]
swivel=next(i for i in items if i['name']=='CasterLSwivel')['object'].Shape
tyre=next(i for i in items if i['name']=='CasterLWheel')['object'].Shape
# Conservatively include the fixed top plate as well as moving fork/wheel in this radius.
caster_vertices=list(swivel.Vertexes)+list(tyre.Vertexes)
radius=max(math.hypot(v.Point.x+P['caster_pivot_x'],v.Point.y-P['caster_pivot_y']) for v in caster_vertices)
sweep={'conservative_radius_mm':radius,'pivot_spacing_mm':2*P['caster_pivot_x'],
       'two_casters_separation_mm':2*P['caster_pivot_x']-2*radius,
       'moving_hardware_top_z':P['caster_top_z'],'base_bottom_z':LOW}
assert sweep['two_casters_separation_mm']>0
assert P['caster_top_z']<LOW
report={'units':'mm','parameters':P,'parts':[{k:v for k,v in i.items() if k not in ('object','color')} for i in items],
        'assembly_bounds_mm':overall,'assembly_size_mm':[overall[k+3]-overall[k] for k in range(3)],
        'four_wheel_ground_z':wheel_ground,'critical_interferences':collisions,'caster_sweep':sweep,
        'battery_fence':{'inner_length':pl,'inner_width':pw,'height':gh,'wall':gw,'floor_thickness_mm':LT,
                          'cable_tie_slots':4,'battery_height_assumed':False,'recess_cut':False},
        'solidcraft_exact_difference_mm3':delta,'upper_group':'UpperAssembly',
        'reference_sha256':REF['sha256'],'power_board_reference':'Original 100x50mm STEP, not the 96x97mm AI PCB'}
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert not collisions,collisions

def apply_style(path):
    gui=ET.Element('Document',{'SchemaVersion':'1','HasExpansion':'1'})
    providers=ET.SubElement(gui,'ViewProviderData',{'Count':str(len(items))})
    for i in items:
        vp=ET.SubElement(providers,'ViewProvider',{'name':i['name'],'expanded':'0'})
        props=ET.SubElement(vp,'Properties',{'Count':'4'})
        for name,typ,value in [('ShapeColor','App::PropertyColor',i['color']),('LineColor','App::PropertyColor',(.13,.15,.17)),('Visibility','App::PropertyBool',True),('DisplayMode','App::PropertyEnumeration',0)]:
            prop=ET.SubElement(props,'Property',{'name':name,'type':typ})
            if typ=='App::PropertyColor':ET.SubElement(prop,'PropertyColor',{'value':str((round(value[0]*255)<<24)|(round(value[1]*255)<<16)|(round(value[2]*255)<<8)|255)})
            elif typ=='App::PropertyBool':ET.SubElement(prop,'Bool',{'value':'true'})
            else:ET.SubElement(prop,'Integer',{'value':'0'})
    tmp=path.with_suffix('.styled.FCStd')
    with zipfile.ZipFile(path) as src,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename!='GuiDocument.xml':dst.writestr(info,src.read(info.filename))
        dst.writestr('GuiDocument.xml',ET.tostring(gui,encoding='utf-8',xml_declaration=True))
    tmp.replace(path)

log('Export native assembly, full STEP, shell STEP and closed individual STL parts')
doc.saveAs(str(HERE/'EdgeMind_Chassis.FCStd'))
shell=[i['object'] for i in items if i['category'] in ('Shell','Mounts') and i['role']=='designed']
Part.export(shell,str(HERE/'EdgeMind_Shell.step'))
Part.export([i['object'] for i in items],str(HERE/'EdgeMind_Assembly.step'))
Part.export([i['object'] for i in items if i['name']!='LowerDeck'],str(HERE/'_assembly-input.step'))
for directory in ('parts-step','parts-stl'):(HERE/directory).mkdir(exist_ok=True)
for i in items:
    if not i['export_part']:continue
    s=i['object'].Shape
    mesh=MeshPart.meshFromShape(Shape=s,LinearDeflection=.12,AngularDeflection=.2,Relative=False)
    assert mesh.isSolid(),i['name']
    mesh.write(str(HERE/'parts-stl'/(i['name']+'.stl')))
    Part.export([i['object']],str(HERE/'parts-step'/(i['name']+'.step')))
mesh_data=[]
log('Tessellate actual assembly for offline preview')
for i in items:
    verts,faces=i['object'].Shape.tessellate(.5)
    mesh_data.append({'name':i['name'],'label':i['label'],'category':i['category'],'color':i['color'],
        'upper_assembly':i['upper_assembly'],'vertices':[[round(v.x,4),round(v.y,4),round(v.z,4)] for v in verts],
        'indices':[list(f) for f in faces]})
(HERE/'preview-meshes.json').write_text(json.dumps(mesh_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
upper.Placement.Base=V(0,0,65);doc.recompute()
doc.saveAs(str(HERE/'EdgeMind_Exploded.FCStd'))
App.closeDocument(doc.Name)
apply_style(HERE/'EdgeMind_Chassis.FCStd')
apply_style(HERE/'EdgeMind_Exploded.FCStd')
log(json.dumps({'parts':len(items),'size_mm':report['assembly_size_mm'],'base_diff_mm3':delta,'collisions':collisions,'wheel_ground':wheel_ground},ensure_ascii=False))
