"""Directly edit the verified V2 geometry; preserve original R3X running gear."""
from pathlib import Path
import json,math,hashlib
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parent
PREV=HERE.parent/'v2-r3x-casters'
P=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
old_report=json.loads((PREV/'verification.json').read_text(encoding='utf-8'))
old_items={p['name']:p for p in old_report['parts']}
print('Open verified V2 native geometry',flush=True)
old=App.openDocument(str(PREV/'EdgeMind_Chassis.FCStd'))
doc=App.newDocument('EdgeMindCameraChassis')
V=App.Vector;LOW=P['lower_deck_bottom_z'];TOP=P['upper_deck_bottom_z']
LT=P['lower_plate_thickness'];UT=P['upper_plate_thickness'];DECK_TOP=TOP+UT
groups={}
for name,label in [('Shell','01 下层一体托盘'),('Mounts','02 安装支撑'),('Wheels','03 万向轮与后驱轮'),('Hardware','04 电机和电源板'),('Fasteners','05 紧固件参考')]:
    g=doc.addObject('App::DocumentObjectGroup',name);g.Label=label;groups[name]=g
upper=doc.addObject('App::Part','UpperAssembly');upper.Label='06 上层总成（含摄像头，可整体抬升）'
items=[]
colors={'shell':(.1,.13,.16),'silver':(.62,.67,.72),'gold':(.86,.57,.13),'board':(.04,.32,.55),'rubber':(.06,.065,.075),'glass':(.02,.16,.25)}
def bounds(s):
    b=s.optimalBoundingBox(False,False);return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def box(x,y,z,dx,dy,dz):return Part.makeBox(dx,dy,dz,V(x,y,z))
def cyl(r,h,p,axis=(0,0,1)):return Part.makeCylinder(r,h,V(*p),V(*axis))
def ring(ro,ri,h,p,axis=(0,0,1)):return cyl(ro,h,p,axis).cut(cyl(ri,h,p,axis))
def polygon(xy,z,h):
    pts=[V(x,y,z) for x,y in xy];return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,h))
def combine(shapes):
    s=shapes[0]
    for other in shapes[1:]:s=s.fuse(other)
    return s.removeSplitter()
def cut(s,tools):return s.cut(Part.makeCompound(tools)).removeSplitter() if tools else s
def rounded_rect(cx,cy,w,l,r,z,h):
    return combine([box(cx-w/2+r,cy-l/2,z,w-2*r,l,h),box(cx-w/2,cy-l/2+r,z,w,l-2*r,h)]+
        [cyl(r,h,(cx+sx*(w/2-r),cy+sy*(l/2-r),z)) for sx in (-1,1) for sy in (-1,1)])
def add(name,label,s,color='shell',category='Shell',role='designed',export=False,is_upper=False,known=None,mesh_shift=(0,0,0),reuse_mesh=None):
    assert not s.isNull() and s.Solids,name
    valid=known['valid'] if known else s.isValid();volume=known['volume_mm3'] if known else s.Volume
    assert valid and volume>0,name
    o=doc.addObject('Part::Feature',name);o.Label=label;o.Shape=s
    o.addProperty('App::PropertyString','DesignRole','Design').DesignRole=role
    o.addProperty('App::PropertyString','DimensionUnit','Design').DimensionUnit='mm'
    if is_upper:upper.addObject(o)
    else:groups[category].addObject(o)
    rgb=colors[color] if isinstance(color,str) else color
    items.append({'name':name,'label':label,'object':o,'color':rgb,'category':category,'role':role,
        'valid':valid,'volume_mm3':volume,'bounds':bounds(s),'solids':len(s.Solids),
        'export_part':export,'upper_assembly':is_upper,'reuse_mesh':reuse_mesh,'mesh_shift':list(mesh_shift)})
    return o

print('Build five-millimetre lower tray with continuous vented perimeter',flush=True)
profile=[(-70,-130),(70,-130),(90,-110),(90,118),(78,130),(-78,130),(-90,118),(-90,-110)]
ref=json.loads((PREV/'reference-extraction.json').read_text(encoding='utf-8'))
v1=json.loads((HERE.parent/'v1-fixed-front-wheels/verification.json').read_text(encoding='utf-8'))
mount_holes=[(x,y,1.7) for x,y,r in ref['rear_bracket_mount_holes_xy_radius']]
mount_holes += [(x,y,1.7) for x in (-76,76) for y in (-111,114)]
caster_holes=[(sx*57+dx,-90+dy,1.7) for sx in (-1,1) for dx in (-15,15) for dy in (-12,12)]
mount_holes += caster_holes
power_holes=[(x-49.992,y-35,1.7) for x,y,r in v1['power_pcb_holes_from_step']]
mount_holes += power_holes
wire_holes=[]
for name in ('MotorLPart19','MotorRPart26'):
    b=old_items[name]['bounds'];cx=(b[0]+b[3])/2;cy=(b[1]+b[4])/2
    wire_holes.append({'connector':name,'center':[cx,cy],'width':P['motor_wire_hole_width'],
        'length':P['motor_wire_hole_length'],'radius':P['motor_wire_hole_corner_radius'],'connector_bounds':b})
floor=polygon(profile,LOW,LT)
tools=[cyl(r,LT+2,(x,y,LOW-1)) for x,y,r in mount_holes]
tools += [box(sx*29.5-1.75,yy-4,LOW-1,3.5,8,LT+2) for sx in (-1,1) for yy in (12,58)]
tools += [rounded_rect(*h['center'],h['width'],h['length'],h['radius'],LOW-1,LT+2) for h in wire_holes]
floor=cut(floor,tools)
pw=49;pl=87;gw=P['battery_guard_wall'];by=P['battery_centre_y'];gh=P['battery_guard_height']
battery=box(-pw/2-gw,by-pl/2-gw,LOW+LT-.5,pw+2*gw,pl+2*gw,gh+.5).cut(box(-pw/2,by-pl/2,LOW+LT-.6,pw,pl,gh+.7))
t=P['perimeter_wall_thickness'];q=t*math.sqrt(2)
inner=[(-70+t*(math.sqrt(2)-1),-130+t),(70-t*(math.sqrt(2)-1),-130+t),
       (90-t,-110+t*(math.sqrt(2)-1)),(90-t,118-t*(math.sqrt(2)-1)),
       (78-t*(math.sqrt(2)-1),130-t),(-78+t*(math.sqrt(2)-1),130-t),
       (-90+t,118-t*(math.sqrt(2)-1)),(-90+t,-110+t*(math.sqrt(2)-1))]
wall=polygon(profile,LOW+LT-.5,P['perimeter_wall_height']+.5).cut(polygon(inner,LOW+LT-.6,P['perimeter_wall_height']+.7))
vents=[box(-46,-131,LOW+LT+z,92,5,3) for z in (6,13)]
vents += [box(-91,yy,LOW+LT+zz,182,ll,3.2) for yy,ll in [(-75,43),(-15,42),(37,22)] for zz in (6,14)]
vents += [box(-30,126,LOW+LT+8,60,5,10)]
wall=cut(wall,vents)
tray=combine([floor,battery,wall])
assert len(tray.Solids)==1
add('LowerTray','5mm下层底板 / 四周连接围栏 / 电池围栏 / 双电机过线孔',tray,export=True)

print('Update upper deck to five millimetres and shift board references',flush=True)
previous_upper=old.getObject('UpperDeck').Shape
bottom_faces=[f for f in previous_upper.Faces if isinstance(f.Surface,Part.Plane) and abs(f.Surface.Axis.z)>.999 and abs(f.CenterOfMass.z-TOP)<.001]
upper_plate=max(bottom_faces,key=lambda f:f.Area).extrude(V(0,0,UT))
upper_plate=cut(upper_plate,[cyl(1.7,UT+2,(x,y,TOP-1)) for x,y in P['camera_foot_hole_xy']])
add('UpperDeck','5mm上层托盘 / 摄像头支架安装孔',upper_plate,export=True,is_upper=True)
for item in old_report['parts']:
    name=item['name']
    if name.startswith(('SidePanel','SideRail','Accent','FrontBumper','FrontCheek','RearBumper')) or name in ('LowerDeck','UpperDeck'):continue
    s=old.getObject(name).Shape.copy();shift=(0,0,0);known=item;reuse=name
    if name.startswith(('FPGA','LPi4A','BoardPost')):
        shift=(0,0,2);s.translate(V(*shift))
    elif name.startswith(('PowerComponent','PowerPost')):
        shift=(0,0,1);s.translate(V(*shift))
    elif name.startswith('MainPost'):
        b=item['bounds'];x=(b[0]+b[3])/2;y=(b[1]+b[4])/2
        s=ring(4.5,1.65,TOP-LOW-LT,(x,y,LOW+LT));known=None;reuse=None
    elif name.startswith('UpperScrew'):
        b=item['bounds'];x=(b[0]+b[3])/2;y=(b[1]+b[4])/2
        s=combine([cyl(1.5,UT+3,(x,y,TOP-3)),cyl(2.8,1.8,(x,y,TOP+UT))]);known=None;reuse=None
    elif name.startswith('CasterBolt'):
        b=item['bounds'];x=(b[0]+b[3])/2;y=(b[1]+b[4])/2
        s=combine([cyl(1.5,LT+23.7811671820691+3,(x,y,31)),cyl(2.8,1.8,(x,y,LOW+LT))]);known=None;reuse=None
    add(name,item['label'],s,item['color'],item['category'],item['role'],item['export_part'],item['upper_assembly'],known,shift,reuse)

print('Build camera bracket, aperture for header and OV5640 reference',flush=True)
cy=P['camera_bracket_y_front'];cw=P['camera_bracket_width'];ct=P['camera_bracket_thickness'];ch=P['camera_bracket_height']
upright=box(-cw/2,cy,DECK_TOP,cw,ct,ch)
foot=box(-cw/2,cy,DECK_TOP,cw,12,3)
gussets=[]
for x in (-19,16):
    pts=[V(x,cy+ct,DECK_TOP+3),V(x,cy+12,DECK_TOP+3),V(x,cy+ct,DECK_TOP+18)]
    gussets.append(Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(3,0,0)))
bracket=combine([upright,foot]+gussets)
pcb_bottom=DECK_TOP+P['camera_board_bottom_above_deck'];mount_z=pcb_bottom+3
def mount_slot(x):
    return combine([box(x-1.6,cy-1,mount_z-1.5,3.2,5,3),cyl(1.6,5,(x,cy-1,mount_z-1.5),(0,1,0)),cyl(1.6,5,(x,cy-1,mount_z+1.5),(0,1,0))])
bracket=cut(bracket,[mount_slot(x) for x in (-12,12)]+[box(-12.5,cy-1,pcb_bottom+21,25,5,10)]+
    [cyl(1.7,5,(x,y,DECK_TOP-1)) for x,y in P['camera_foot_hole_xy']])
add('CameraBracket','摄像头立板 / 24mm孔距 / 可调槽 / 排针避让窗',bracket,'silver','Mounts',export=True,is_upper=True)
pcb_front=cy-4;pcb_back=pcb_front+1.6;lens_z=pcb_bottom+10
camera_pcb=cut(box(-15,pcb_front,pcb_bottom,30,1.6,30),[cyl(1.6,3,(x,pcb_front-.5,mount_z),(0,1,0)) for x in (-12,12)])
add('CameraPCB','OV5640摄像头30×30安装参考',camera_pcb,'board','Hardware','camera_reference',is_upper=True)
housing=box(-7,pcb_front-5.6,lens_z-7,14,5.6,14)
lens=combine([housing,cyl(7,12.6,(0,pcb_front-5.6,lens_z),(0,-1,0)),cyl(6,7,(0,pcb_front-18.2,lens_z),(0,-1,0)),cyl(7,7.8,(0,pcb_front-25.2,lens_z),(0,-1,0))])
lens=cut(lens,[cyl(5.2,1.2,(0,pcb_front-33.1,lens_z),(0,1,0))])
add('CameraLens','镜头包络φ14 / 总前伸33mm为参考',lens,'rubber','Hardware','camera_reference',is_upper=True)
add('CameraGlass','镜头前片参考',cyl(5,.4,(0,pcb_front-32.7,lens_z),(0,1,0)),'glass','Hardware','camera_reference',is_upper=True)
add('CameraHeader','摄像头2×9排针绝缘座参考',box(-11.43,pcb_back,pcb_bottom+22.69,22.86,2.5,5.08),'rubber','Hardware','camera_reference',is_upper=True)
pins=[box(-10.16+i*2.54-.32,pcb_back-.3,pcb_bottom+23.96+j*2.54-.32,.64,8,.64) for i in range(9) for j in range(2)]
add('CameraPins','18根2.54mm排针参考',Part.makeCompound(pins),'gold','Hardware','camera_reference',is_upper=True)
for i,x in enumerate((-12,12),1):
    add('CameraSpacer'+str(i),'摄像头2.4mm隔柱参考'+str(i),ring(2.5,1.4,2.4,(x,pcb_back,mount_z),(0,1,0)),'gold','Mounts','mount_reference',is_upper=True)
    screw=combine([cyl(1.25,9,(x,pcb_front,mount_z),(0,1,0)),cyl(2.3,1.6,(x,pcb_front-1.6,mount_z),(0,1,0))])
    add('CameraScrew'+str(i),'摄像头M2.5螺钉参考'+str(i),screw,'silver','Fasteners','fastener_reference',is_upper=True)
for i,(x,y) in enumerate(P['camera_foot_hole_xy'],1):
    screw=combine([cyl(1.5,10,(x,y,DECK_TOP-7)),cyl(2.8,1.8,(x,y,DECK_TOP+3))])
    add('CameraFootScrew'+str(i),'立板M3底座螺钉参考'+str(i),screw,'silver','Fasteners','fastener_reference',is_upper=True)

doc.recompute()
print('Check changed geometry against boards, motor connectors and camera',flush=True)
collisions=[]
designed=[i for i in items if i['role']=='designed' and i['category'] in ('Shell','Mounts')]
targets=[i for i in items if i['role'] in ('source_geometry','camera_reference') or i['name'].startswith(('FPGA','LPi4A'))]
for a in designed:
    for b in targets:
        if a['name']==b['name']:continue
        sa,sb=a['object'].Shape,b['object'].Shape
        if not sa.BoundBox.intersect(sb.BoundBox):continue
        volume=sa.common(sb).Volume
        if volume>.02:collisions.append({'a':a['name'],'b':b['name'],'volume_mm3':volume})
for h in wire_holes:
    cx,yy=h['center']
    probe=rounded_rect(cx,yy,h['width']-.02,h['length']-.02,h['radius']-.01,LOW-.5,LT+1)
    assert tray.common(probe).Volume<.001
    b=h['connector_bounds'];assert abs(cx-(b[0]+b[3])/2)<1e-6 and abs(yy-(b[1]+b[4])/2)<1e-6
plate_z=[bounds(tray)[2],bounds(upper_plate)[2]]
wheel_ground=[next(i for i in items if i['name']==n)['bounds'][2] for n in ['RearLWheel','RearRWheel','CasterLWheel','CasterRWheel']]
assert max(abs(z) for z in wheel_ground)<.001
bs=[i['bounds'] for i in items];overall=[min(b[k] for b in bs) for k in range(3)]+[max(b[k] for b in bs) for k in range(3,6)]
report={'units':'mm','parameters':P,'parts':[{k:v for k,v in i.items() if k!='object'} for i in items],
    'assembly_bounds_mm':overall,'assembly_size_mm':[overall[k+3]-overall[k] for k in range(3)],
    'four_wheel_ground_z':wheel_ground,'critical_interferences':collisions,'caster_sweep':old_report['caster_sweep'],
    'motor_wire_holes':wire_holes,'continuous_perimeter':{'single_solid_tray':True,'front_left_right_joined':True,'vents_retained':True,'upper_side_rails_removed':True},
    'plate_thicknesses_mm':{'R3X_reference':5,'lower':LT,'upper':UT},
    'battery_fence':dict(old_report['battery_fence'],floor_thickness_mm=LT),
    'camera':{'board_size_mm':[30,30],'mount_pitch_mm':24,'header_clearance_window_mm':[25,10],
        'bracket_slots_mm':[3.2,6.2],'camera_board_bottom_z':pcb_bottom,'lens_axis_z':lens_z,
        'source':'references/OV5640-mechanical-drawing.png','assumptions':P['camera_reference_notes']},
    'reference_sha256':old_report['reference_sha256'],'power_board_reference':old_report['power_board_reference'],
    'previous_native_sha256':hashlib.sha256((PREV/'EdgeMind_Chassis.FCStd').read_bytes()).hexdigest()}
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert not collisions,collisions
doc.saveAs(str(HERE/'EdgeMind_Chassis.FCStd'))
App.closeDocument(doc.Name);App.closeDocument(old.Name)
print(json.dumps({'objects':len(items),'STEP_solids':sum(i['solids'] for i in items),'plate_thicknesses_mm':report['plate_thicknesses_mm'],
 'interferences':collisions,'wire_holes':wire_holes},ensure_ascii=False),flush=True)
