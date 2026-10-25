"""Add a third sensor deck to the verified V3; retain V3 source geometry."""
from pathlib import Path
import hashlib, json, math
import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
PREV = HERE.parent/'v3-camera-closed-rails'
P = json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
old_report = json.loads((PREV/'verification.json').read_text(encoding='utf-8'))
old = App.openDocument(str(PREV/'EdgeMind_Chassis.FCStd'))
doc = App.newDocument('EdgeMindLidarIMUChassis')
V = App.Vector
middle_top = old_report['parameters']['upper_deck_bottom_z'] + 5
Z = middle_top + P['third_support_height']
T = P['third_plate_thickness']; ZTOP = Z+T
groups = {}
for name,label in [('Shell','01 下层托盘'),('Mounts','02 底盘安装支撑'),('Wheels','03 原轮组'),('Hardware','04 电机与电源板'),('Fasteners','05 紧固件参考')]:
    g=doc.addObject('App::DocumentObjectGroup',name);g.Label=label;groups[name]=g
upper=doc.addObject('App::Part','UpperAssembly');upper.Label='06 第二层总成（原V3上层与摄像头）'
third=doc.addObject('App::Part','ThirdAssembly');third.Label='07 第三层总成（LD06、+X侧MPU6050、后方洞洞板）'
third.addProperty('App::PropertyLength','PlateThickness','Design').PlateThickness=T
third.addProperty('App::PropertyLength','SupportHeight','Design').SupportHeight=P['third_support_height']
third.addProperty('App::PropertyString','ParameterSource','Design').ParameterSource='parameters.json; rebuild with build_model.py'
items=[]
colors={'shell':(.15,.20,.25),'silver':(.67,.72,.77),'gold':(.84,.58,.18),'board':(.05,.30,.66),'black':(.065,.072,.085)}
def bounds(s):
    b=s.optimalBoundingBox(False,False);return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def box(x,y,z,dx,dy,dz):return Part.makeBox(dx,dy,dz,V(x,y,z))
def cyl(r,h,p):return Part.makeCylinder(r,h,V(*p))
def ring(ro,ri,h,p):return cyl(ro,h,p).cut(cyl(ri,h,p))
def combine(ss):
    s=ss[0]
    for b in ss[1:]:s=s.fuse(b)
    return s.removeSplitter()
def cut(s,tools):return s.cut(Part.makeCompound(tools)).removeSplitter()
def rounded_rect(cx,cy,w,l,r,z,h):
    return combine([box(cx-w/2+r,cy-l/2,z,w-2*r,l,h),box(cx-w/2,cy-l/2+r,z,w,l-2*r,h)]+
        [cyl(r,h,(cx+sx*(w/2-r),cy+sy*(l/2-r),z)) for sx in (-1,1) for sy in (-1,1)])
def capsule(cx,cy,w,l,z,h):
    r=w/2; d=(l-w)/2
    return combine([box(cx-r,cy-d,z,w,2*d,h),cyl(r,h,(cx,cy-d,z)),cyl(r,h,(cx,cy+d,z))])
def add(name,label,s,color='shell',category='Shell',role='designed',layer=3,export=False,known=None):
    assert not s.isNull() and s.Solids,name
    valid=known['valid'] if known else s.isValid();assert valid,name
    o=doc.addObject('Part::Feature',name);o.Label=label;o.Shape=s
    o.addProperty('App::PropertyString','DesignRole','Design').DesignRole=role
    o.addProperty('App::PropertyString','DimensionUnit','Design').DimensionUnit='mm'
    if layer==3:third.addObject(o)
    elif layer==2:upper.addObject(o)
    else:groups[category].addObject(o)
    rgb=colors[color] if isinstance(color,str) else color
    items.append({'name':name,'label':label,'object':o,'category':category,'role':role,'color':list(rgb),
                  'layer':layer,'upper_assembly':layer==2,'third_assembly':layer==3,
                  'valid':valid,'volume_mm3':s.Volume if known is None else known['volume_mm3'],
                  'bounds':bounds(s) if known is None else known['bounds'],'solids':len(s.Solids),'export_part':export,'reuse_previous_mesh':known is not None})
    return o

print('Copy verified V3 at original placement',flush=True)
for p in old_report['parts']:
    if p['name'].startswith('UpperScrew'):continue
    add(p['name'],p['label'],old.getObject(p['name']).Shape.copy(),p['color'],p['category'],p['role'],
        2 if p['upper_assembly'] else 1,False,p)

# Recover mounting bore centers from the actual LD06 analytic faces, excluding
# the two already-installed M2 housing screws on the other diagonal.
source=Part.read(str(HERE/'references/LD06_LiDAR.STEP'))
cx,by,cz=P['lidar_source_axis_point'];lx,ly=P['lidar_center_xy']
bottom_lift=P['lidar_post_height']-P['lidar_bottom_counterbore_depth_from_step']
lidar_bottom=ZTOP+bottom_lift
mounts={}
for f in source.Solids[0].Faces:
    s=f.Surface
    if isinstance(s,Part.Cylinder) and abs(s.Radius-2.4)<1e-6 and abs(s.Axis.y)>.999:
        x=s.Center.x-cx+lx;y=cz-s.Center.z+ly
        mounts[(round(x,6),round(y,6))]=[x,y]
lidar_holes=sorted(mounts.values());assert len(lidar_holes)==2
assert all(abs(abs(lidar_holes[1][i]-lidar_holes[0][i])-28.2)<1e-6 for i in (0,1))

ix,iy=P['imu_center_xy'];iw,il=P['imu_board_size_xy'];ip=P['imu_hole_pitch_reference']
imu_side=P['imu_outer_side_x_sign'];assert imu_side in (-1,1)
imu_holes=[[ix+imu_side*(iw/2-P['imu_hole_edge_offset_reference']),iy+sy*ip/2] for sy in (-1,1)]
header_x=ix-imu_side*(iw/2-1.27)
perf_path=HERE/'references/3D_PCB2_2026-10-20.step'
perf=Part.read(str(perf_path));assert len(perf.Solids)==1
pb=bounds(perf);px,py=P['perfboard_center_xy'];pcx=(pb[0]+pb[3])/2;pcy=(pb[1]+pb[4])/2
perf_hole_map={}
for f in perf.Faces:
    surf=f.Surface
    if isinstance(surf,Part.Cylinder) and abs(surf.Radius-1.5)<.001 and abs(surf.Axis.z)>.999:
        x=surf.Center.x-pcx+px;y=surf.Center.y-pcy+py
        perf_hole_map[(round(x,6),round(y,6))]=[x,y]
perf_holes=sorted(perf_hole_map.values());assert len(perf_holes)==4
perf_z=ZTOP+P['perfboard_spacer_height'];perf.translate(V(px-pcx,py-pcy,perf_z-pb[2]))
profile=[(-70,-130),(70,-130),(90,-110),(90,118),(78,130),(-78,130),(-90,118),(-90,-110)]
points=[V(x,y,Z) for x,y in profile];plate=Part.Face(Part.makePolygon(points+[points[0]])).extrude(V(0,0,T))
tools=[cyl(P['third_support_clearance_diameter']/2,T+2,(x,y,Z-1)) for x,y in P['third_support_holes_xy']]
tools += [cyl(P['lidar_mount_clearance_diameter']/2,T+2,(x,y,Z-1)) for x,y in lidar_holes]
tools += [capsule(x,y,*P['imu_plate_mount_slot_size_xy'],Z-1,T+2) for x,y in imu_holes]
tools += [cyl(P['perfboard_plate_hole_diameter']/2,T+2,(x,y,Z-1)) for x,y in perf_holes]
wire_slots=[P['lidar_wire_slot'],P['imu_wire_slot']]+P.get('additional_wire_slots',[])
assert abs(P['imu_wire_slot'][0]-header_x)<1e-8 and abs(P['imu_wire_slot'][1]-iy)<1e-8
assert P['imu_wire_slot'][3]>=20.32
assert P['lidar_wire_slot'][1]-P['lidar_wire_slot'][3]/2>ly+19.295
tools += [rounded_rect(*slot,Z-1,T+2) for slot in wire_slots]
vent_slots=[(x,y,12,32 if y==-29 else 46,3) for x in (-46,-23,0,23,46) for y in (-29,34,97)]
tools += [rounded_rect(*slot,Z-1,T+2) for slot in vent_slots]
plate=cut(plate,tools);assert len(plate.Solids)==1
add('ThirdDeck','第三层5mm传感器板 / 雷达正前中央 / MPU在+X侧孔朝外',plate,export=True)
for i,(x,y) in enumerate(P['third_support_holes_xy'],1):
    # Male stud passes through the second deck into the existing lower post.
    # A screw head underneath would collide with that existing lower post.
    post=combine([cyl(4.5,P['third_support_height'],(x,y,middle_top)),cyl(1.5,8.5,(x,y,middle_top-8))])
    post=cut(post,[cyl(1.65,11,(x,y,Z-10))])
    add('ThirdPost'+str(i),'第三层M3单头支柱45mm / 下端8mm螺柱参考'+str(i),post,'gold','Mounts','mount_reference')
    screw=combine([cyl(1.5,8,(x,y,ZTOP-8)),cyl(2.8,1.8,(x,y,ZTOP))])
    add('ThirdScrew'+str(i),'第三层M3上固定螺钉参考'+str(i),screw,'silver','Fasteners','fastener_reference')

print('Place source LD06 geometry and exact diagonal mounting posts',flush=True)
for i,s in enumerate(source.Solids):
    s=s.copy();s.translate(V(-cx,-by,-cz));s.rotate(V(0,0,0),V(1,0,0),90);s.translate(V(lx,ly,lidar_bottom))
    color='black' if i==0 else ('silver' if i in (1,2) else (.8,.8,.75))
    add('LidarSource'+str(i),'LD06原始STEP / '+['主体','原装壳体螺钉A','原装壳体螺钉B','连接器'][i],s,color,'Hardware','source_geometry')
for i,(x,y) in enumerate(lidar_holes,1):
    add('LidarPost'+str(i),'雷达M2双通圆隔柱φ4×18参考'+str(i),ring(2,1.05,18,(x,y,ZTOP)),'gold','Mounts','mount_reference')
    # 1 mm flange above 11.8 mm counterbore; M2x4 leaves 3 mm engagement.
    head_z=lidar_bottom+12.8
    add('LidarTopScrew'+str(i),'雷达M2×4上锁螺钉参考'+str(i),combine([cyl(1,4,(x,y,head_z-4)),cyl(1.8,1.4,(x,y,head_z))]),'silver','Fasteners','fastener_reference')
    add('LidarBottomScrew'+str(i),'雷达隔柱M2×8底锁螺钉参考'+str(i),combine([cyl(1,8,(x,y,Z)),cyl(1.8,1.4,(x,y,Z-1.4))]),'silver','Fasteners','fastener_reference')

print('Build GY-521 on corrected side, mounting holes outward/header inward',flush=True)
pcb_z=ZTOP+P['imu_spacer_height'];pcb_t=P['imu_pcb_thickness_reference']
pin_holes=[cyl(.48,pcb_t+6,(header_x,iy+(n-3.5)*2.54,pcb_z-1)) for n in range(8)]
pcb=cut(box(ix-iw/2,iy-il/2,pcb_z,iw,il,pcb_t),[cyl(1.5,pcb_t+2,(x,y,pcb_z-1)) for x,y in imu_holes]+pin_holes)
add('IMUPCB','GY-521 MPU6050 / 15.56012×20.26185 / 安装孔向+X外侧',pcb,'board','Hardware','imu_reference')
add('IMUChip','MPU6050芯片位置与高度参考',box(ix-2,iy-2,pcb_z+pcb_t,4,4,.9),'black','Hardware','imu_reference')
add('IMUHeader','GY-521 1×8排针绝缘座 / 朝向车内',cut(box(header_x-1.27,iy-10.16,pcb_z+pcb_t,2.54,20.32,2.54),pin_holes),'black','Hardware','imu_reference')
pins=[box(header_x-.32,iy+(n-3.5)*2.54-.32,pcb_z-2,.64,.64,10) for n in range(8)]
add('IMUPins','GY-521 8针 / 2.54mm间距 / 高度参考',Part.makeCompound(pins),'gold','Hardware','imu_reference')
for i,(x,y) in enumerate(imu_holes,1):
    add('IMUSpacer'+str(i),'MPU M2.5绝缘隔柱6mm参考'+str(i),ring(2.25,1.4,6,(x,y,ZTOP)),'silver','Mounts','mount_reference')
    add('IMUTopScrew'+str(i),'MPU M2.5×4上螺钉参考'+str(i),combine([cyl(1.25,4,(x,y,pcb_z+pcb_t-4)),cyl(2.15,1.6,(x,y,pcb_z+pcb_t))]),'silver','Fasteners','fastener_reference')
    add('IMUBottomScrew'+str(i),'MPU M2.5底螺钉参考'+str(i),combine([cyl(1.25,8,(x,y,Z)),cyl(2.15,1.6,(x,y,Z-1.6))]),'silver','Fasteners','fastener_reference')
print('Place supplied perfboard behind lidar, preserve all source perforations',flush=True)
add('PerfboardSource','洞洞板 / 用户2026-10-20 STEP / 雷达后方居中',perf,(.04,.47,.72),'Hardware','source_geometry')
for i,(x,y) in enumerate(perf_holes,1):
    add('PerfboardSpacer'+str(i),'洞洞板M2.5绝缘隔柱8mm参考'+str(i),ring(2.5,1.4,8,(x,y,ZTOP)),'silver','Mounts','mount_reference')
    add('PerfboardTopScrew'+str(i),'洞洞板M2.5×6上螺钉参考'+str(i),combine([cyl(1.25,6,(x,y,perf_z+pb[5]-pb[2]-6)),cyl(2.15,1.6,(x,y,perf_z+pb[5]-pb[2]))]),'silver','Fasteners','fastener_reference')
    add('PerfboardBottomScrew'+str(i),'洞洞板M2.5×8底螺钉参考'+str(i),combine([cyl(1.25,8,(x,y,Z)),cyl(2.15,1.6,(x,y,Z-1.6))]),'silver','Fasteners','fastener_reference')
doc.recompute()
print('Check all added solids against each other and the previous assembly',flush=True)
new=[i for i in items if not i['reuse_previous_mesh']];collisions=[]
for a_idx,a in enumerate(items):
    for b in items[a_idx+1:]:
        if a['reuse_previous_mesh'] and b['reuse_previous_mesh']:continue
        sa,sb=a['object'].Shape,b['object'].Shape
        if not sa.BoundBox.intersect(sb.BoundBox):continue
        # Installed source parts belong to one supplied assembly.
        if a['name'].startswith('LidarSource') and b['name'].startswith('LidarSource'):continue
        volume=sa.common(sb).Volume
        if volume>.015:collisions.append({'a':a['name'],'b':b['name'],'volume_mm3':volume})
camera_gap=Z-old.getObject('CameraBracket').Shape.BoundBox.ZMax
board_top=max(p['bounds'][5] for p in old_report['parts'] if p['name'].startswith(('FPGA','LPi4A')))
report={'units':'mm','parameters':P,'parts':[{k:v for k,v in i.items() if k!='object'} for i in items],
        'third_deck_bottom_z':Z,'third_deck_top_z':ZTOP,'camera_bracket_clearance_mm':camera_gap,
        'board_reference_clearance_mm':Z-board_top,'plate_thicknesses_mm':{'lower':5,'second':5,'third':T},
        'lidar':{'source_sha256':hashlib.sha256((HERE/'references/LD06_LiDAR.STEP').read_bytes()).hexdigest(),
                 'center_xy':P['lidar_center_xy'],'source_rotation_x_degrees':90,'scale':1,
                 'base_z':lidar_bottom,'base_clearance_mm':bottom_lift,'mount_holes_xy':lidar_holes,
                 'mount_pitch_xy_mm':[28.2,28.2],'counterbore_diameter_mm':4.8,'counterbore_depth_mm':11.8,
                 'source_through_diameter_mm':2.5,'model_height_mm':33.3,'post_mm':{'outer_diameter':4,'length':18},
                 'top_screw_reference':'M2x4; 1mm flange plus 3mm engagement','bottom_screw_reference':'M2x8; 5mm plate plus 3mm engagement'},
        'imu':{'drawing_sha256':hashlib.sha256((HERE/'references/MPU6050-V1_尺寸图.jpg').read_bytes()).hexdigest(),
               'center_xy':P['imu_center_xy'],'mount_holes_xy_reference':imu_holes,'header_x':header_x,
               'holes_face':f'outward_{imu_side:+d}X','header_faces':f'inward_{-imu_side:+d}X','board_size_mm':P['imu_board_size_xy'],
               'hole_pitch_reference_mm':ip,'plate_slots_mm':P['imu_plate_mount_slot_size_xy'],
               'geometry_status':'board outline and phi3 holes dimensioned; center locations and component heights are reference estimates'},
        'wire_slots':wire_slots,'vent_slots':vent_slots,'critical_interferences':collisions,
        'perfboard':{'source_sha256':hashlib.sha256(perf_path.read_bytes()).hexdigest(),'source_size_mm':[pb[k+3]-pb[k] for k in range(3)],
                     'source_faces':len(perf.Faces),'source_volume_mm3':perf.Volume,'center_xy':P['perfboard_center_xy'],
                     'mount_holes_xy':perf_holes,'source_mount_diameter_mm':3.000006,'plate_hole_diameter_mm':P['perfboard_plate_hole_diameter'],
                     'pcb_bottom_z':perf_z,'spacer_height_mm':8,'lidar_to_board_edge_gap_mm':bounds(perf)[1]-(ly+19.295),
                     'geometry_status':'exact source geometry at scale 1, translated only; no components present in source STEP'},
        'previous_native_sha256':hashlib.sha256((PREV/'EdgeMind_Chassis.FCStd').read_bytes()).hexdigest(),
        'inherited_reference_limits':['FPGA and LPi4A are V3 envelopes','Camera is V3 drawing-based reference','Power PCB is V3 old 100x50 STEP','No load/thermal/vibration/cable-bend validation']}
bs=[i['bounds'] for i in items];report['assembly_bounds_mm']=[min(b[k] for b in bs) for k in range(3)]+[max(b[k] for b in bs) for k in range(3,6)]
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert camera_gap>=2.99
assert not collisions,collisions
doc.saveAs(str(HERE/'EdgeMind_Chassis.FCStd'))
App.closeDocument(doc.Name);App.closeDocument(old.Name)
print(json.dumps({'parts':len(items),'third_bottom':Z,'third_top':ZTOP,'camera_gap':camera_gap,'board_gap':Z-board_top,'new_parts':len(new),'collisions':collisions}),flush=True)
