"""V5 screen trial: preserve V4 sensors, rotate/move perfboard, rebuild third deck."""
from pathlib import Path
import json,hashlib,itertools
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'v4-lidar-imu'
P=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
R=json.loads((BASE/'verification.json').read_text(encoding='utf-8'))
old=App.openDocument(str(BASE/'EdgeMind_Chassis.FCStd'))
doc=App.newDocument('EdgeMindRGBTouchChassis');V=App.Vector
Z=R['third_deck_bottom_z'];T=P['third_plate_thickness'];ZT=Z+T
groups={}
for name,label in [('Shell','01 下层托盘'),('Mounts','02 底盘支撑'),('Wheels','03 原轮组'),('Hardware','04 电机与电源板'),('Fasteners','05 紧固件参考')]:
    g=doc.addObject('App::DocumentObjectGroup',name);g.Label=label;groups[name]=g
upper=doc.addObject('App::Part','UpperAssembly');upper.Label='06 第二层与摄像头'
third=doc.addObject('App::Part','ThirdAssembly');third.Label='07 第三层 / 左侧竖屏 / 右侧纵向洞洞板'
colors={'plate':(.15,.20,.25),'pcb':(.035,.055,.075),'metal':(.60,.65,.69),'glass':(.012,.048,.07),'silver':(.67,.72,.77),'black':(.07,.075,.08)}
items=[]
def box(x,y,z,w,l,h):return Part.makeBox(w,l,h,V(x,y,z))
def cyl(r,h,x,y,z):return Part.makeCylinder(r,h,V(x,y,z))
def ring(ro,ri,h,x,y,z):return cyl(ro,h,x,y,z).cut(cyl(ri,h,x,y,z))
def bounds(s):
    b=s.optimalBoundingBox(False,False);return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def unite(parts):
    s=parts[0]
    for t in parts[1:]:s=s.fuse(t)
    return s.removeSplitter()
def cut(s,tools):return s.cut(Part.makeCompound(tools)).removeSplitter()
def rr(x,y,w,l,r,z,h):
    return unite([box(x-w/2+r,y-l/2,z,w-2*r,l,h),box(x-w/2,y-l/2+r,z,w,l-2*r,h)]+[cyl(r,h,x+sx*(w/2-r),y+sy*(l/2-r),z) for sx in (-1,1) for sy in (-1,1)])
def capsule(x,y,w,l,z,h):
    r=w/2;d=(l-w)/2
    return unite([box(x-r,y-d,z,w,2*d,h),cyl(r,h,x,y-d,z),cyl(r,h,x,y+d,z)])
def add(name,label,s,color,category='Hardware',role='screen_reference',layer=3,known=None,mesh_rotation=0,mesh_translation=(0,0,0),export=False):
    assert not s.isNull() and s.Solids,name
    valid=known['valid'] if known else s.isValid();assert valid,name
    o=doc.addObject('Part::Feature',name);o.Label=label;o.Shape=s
    o.addProperty('App::PropertyString','DesignRole','Design').DesignRole=role
    if layer==3:third.addObject(o)
    elif layer==2:upper.addObject(o)
    else:groups[category].addObject(o)
    rgb=colors[color] if isinstance(color,str) else color
    items.append({'name':name,'label':label,'object':o,'category':category,'role':role,'color':list(rgb),'layer':layer,
      'upper_assembly':layer==2,'third_assembly':layer==3,'valid':valid,'volume_mm3':known['volume_mm3'] if known else s.Volume,
      'bounds':bounds(s) if (not known or mesh_rotation) else known['bounds'],'solids':len(s.Solids),'export_part':export,
      'reuse_previous_mesh':bool(known),'mesh_rotation_z':mesh_rotation,'mesh_translation':list(mesh_translation)})
    return o

print('Reuse V4 native geometry; move/rotate complete perfboard assembly',flush=True)
for p in R['parts']:
    if p['name']=='ThirdDeck':continue
    s=old.getObject(p['name']).Shape.copy();moved=p['name'].startswith('Perfboard')
    if moved:s.rotate(V(0,0,0),V(0,0,1),90);s.translate(V(0,-20,0))
    label=p['label'] if not moved else p['label'].replace('雷达后方居中','右移37mm / 平面内旋转90°')
    add(p['name'],label,s,p['color'],p['category'],p['role'],p['layer'],known=p,mesh_rotation=90 if moved else 0,mesh_translation=(0,-20,0) if moved else (0,0,0))

by_name=lambda n:next(i for i in items if i['name']==n)
perf_holes=[[-y,x-20] for x,y in R['perfboard']['mount_holes_xy']]
sx,sy=P['screen_center_xy'];sw,sl=P['screen_pcb_size_xy_reference'];px,py=P['screen_mount_pitch_xy_reference']
screen_holes=[[sx+dx*px/2,sy+dy*py/2] for dx in (-1,1) for dy in (-1,1)]
profile=[(-70,-130),(70,-130),(90,-110),(90,118),(78,130),(-78,130),(-90,118),(-90,-110)]
pts=[V(x,y,Z) for x,y in profile];plate=Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,T))
tools=[cyl(1.7,T+2,x,y,Z-1) for x,y in P['third_support_holes_xy']]
tools += [cyl(1.15,T+2,x,y,Z-1) for x,y in R['lidar']['mount_holes_xy']]
tools += [capsule(x,y,*P['imu_plate_mount_slot_size_xy'],Z-1,T+2) for x,y in R['imu']['mount_holes_xy_reference']]
tools += [cyl(1.4,T+2,x,y,Z-1) for x,y in perf_holes]
tools += [capsule(x,y,*P['screen_plate_mount_slot_xy'],Z-1,T+2) for x,y in screen_holes]
wire_slots=[P['lidar_wire_slot'],P['imu_wire_slot']]+P['additional_wire_slots']+[P['screen_wire_slot']]
tools += [rr(*s,Z-1,T+2) for s in wire_slots+P['vent_slots']]
plate=cut(plate,tools);assert len(plate.Solids)==1
add('ThirdDeck','V5第三层5mm板 / 竖屏与纵向洞洞板固定孔',plate,'plate','Shell','designed',export=True)

print('Build flat portrait 4.3-inch LCD/touch module installation reference',flush=True)
pcb_z=ZT+P['screen_spacer_height_reference'];pcb_t=P['screen_pcb_thickness_reference']
pcb=cut(box(sx-sw/2,sy-sl/2,pcb_z,sw,sl,pcb_t),[cyl(P['screen_pcb_mount_diameter_reference']/2,pcb_t+2,x,y,pcb_z-1) for x,y in screen_holes])
add('ScreenPCB','4.3寸模块PCB 116×67.2×1.6参考 / 四孔距待实测',pcb,'pcb')
lw,ll=P['screen_lcd_size_xy_from_pdf'];aw,al=P['screen_active_area_xy_from_pdf'];lcd_z=pcb_z+pcb_t;lt=P['screen_lcd_touch_thickness_from_pdf']
frame=unite([box(sx-lw/2,sy-ll/2,lcd_z,lw,ll,lt-.25),
    box(sx-lw/2,sy-ll/2,lcd_z+lt-.25,lw,ll,.25).cut(box(sx-aw/2,sy-al/2,lcd_z+lt-.35,aw,al,.5))])
add('ScreenLCDFrame','AT043TN24含触摸 105.5×67.2×4.05 / 厂家PDF外形',frame,'metal')
add('ScreenActiveGlass','竖屏可视区域 95.04×53.856 / 480×272物理分辨率',box(sx-aw/2,sy-al/2,lcd_z+lt-.25,aw,al,.25),'glass')
cw,cl,ch=P['screen_back_connector_envelope_reference'];cy=P['screen_back_connector_center_y']
add('ScreenBackInterface','屏幕背面接口43.18×5.08×9参考包络 / 位置高度待实测',box(sx-cw/2,cy-cl/2,pcb_z-ch,cw,cl,ch),'black')
for i,(x,y) in enumerate(screen_holes,1):
    add('ScreenPost'+str(i),'屏幕M3绝缘隔柱12mm参考'+str(i),ring(3,1.65,12,x,y,ZT),'silver','Mounts','mount_reference')
    add('ScreenTopScrew'+str(i),'屏幕M3×6上螺钉参考'+str(i),unite([cyl(1.5,6,x,y,pcb_z+pcb_t-6),cyl(2.8,1.8,x,y,pcb_z+pcb_t)]),'silver','Fasteners','fastener_reference')
    add('ScreenBottomScrew'+str(i),'屏幕M3×8底螺钉参考'+str(i),unite([cyl(1.5,8,x,y,Z),cyl(2.8,1.8,x,y,Z-1.8)]),'silver','Fasteners','fastener_reference')
doc.recompute()
print('Check screen, rotated board, third plate and all assembly clearances',flush=True)
changed=[i for i in items if i['name']=='ThirdDeck' or i['name'].startswith(('Screen','Perfboard'))]
collisions=[]
for a,b in itertools.combinations(items,2):
    if a not in changed and b not in changed:continue
    sa,sb=a['object'].Shape,b['object'].Shape
    if not sa.BoundBox.intersect(sb.BoundBox):continue
    volume=sa.common(sb).Volume
    if volume>.015:collisions.append({'a':a['name'],'b':b['name'],'volume_mm3':volume})
screen_shape=Part.makeCompound([i['object'].Shape for i in items if i['name'].startswith('Screen')])
lidar_shape=by_name('LidarSource0')['object'].Shape;perf_shape=by_name('PerfboardSource')['object'].Shape
screen_lidar_gap=screen_shape.distToShape(lidar_shape)[0]
screen_perf_gap=screen_shape.distToShape(perf_shape)[0]
screen_top=max(i['bounds'][5] for i in items if i['name'].startswith('Screen'))
optical_z=R['lidar']['base_z']+20.7
report={k:v for k,v in R.items() if k in ('units','lidar','imu','camera_bracket_clearance_mm','board_reference_clearance_mm','plate_thicknesses_mm','third_deck_bottom_z','third_deck_top_z','inherited_reference_limits')}
report.update({'parameters':P,'parts':[{k:v for k,v in i.items() if k!='object'} for i in items],
 'previous_native_sha256':hashlib.sha256((BASE/'EdgeMind_Chassis.FCStd').read_bytes()).hexdigest(),
 'mesh_cache_directory':'v4-lidar-imu','wire_slots':wire_slots,'vent_slots':P['vent_slots'],'critical_interferences':collisions,
 'perfboard':dict(R['perfboard'],center_xy=P['perfboard_center_xy'],rotation_z_degrees=90,mount_holes_xy=perf_holes,
                  lidar_to_board_edge_gap_mm=perf_shape.BoundBox.YMin-lidar_shape.BoundBox.YMax,
                  assembly_size_xy_mm=[perf_shape.BoundBox.XLength,perf_shape.BoundBox.YLength],geometry_status='V4 source geometry rigidly rotated 90 degrees and moved right; face count/volume preserved'),
 'screen':{'center_xy':P['screen_center_xy'],'orientation':'portrait in XY plane, face up; long edge parallel vehicle Y',
  'module_outline_xy_mm':P['screen_pcb_size_xy_reference'],'lcd_outline_from_pdf_xy_mm':P['screen_lcd_size_xy_from_pdf'],
  'lcd_touch_thickness_from_pdf_mm':lt,'active_area_from_pdf_xy_mm':P['screen_active_area_xy_from_pdf'],
  'module_mount_holes_xy_reference':screen_holes,'module_mount_pitch_reference_mm':P['screen_mount_pitch_xy_reference'],
  'plate_mount_slot_xy_mm':P['screen_plate_mount_slot_xy'],'standoff_height_reference_mm':12,
  'pcb_bottom_z':pcb_z,'module_top_z':screen_top,'screen_lidar_gap_mm':screen_lidar_gap,'screen_perfboard_gap_mm':screen_perf_gap,
  'screen_to_optical_zone_vertical_gap_mm':optical_z-screen_top,'back_connector_to_deck_gap_mm':pcb_z-ch-ZT,
  'outer_plate_edge_gap_mm':(sx-sw/2)+90,
  'module_mount_status':'provisional: photo-based 112x56 pitch; full PCB mechanical drawing/back height not supplied',
  'pdf_source':'references/AT043TN24-V1.pdf; physical PDF pages 4,18,25',
  'source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (HERE/'references').iterdir() if f.is_file()}}
})
bs=[i['bounds'] for i in items];report['assembly_bounds_mm']=[min(b[k] for b in bs) for k in range(3)]+[max(b[k] for b in bs) for k in range(3,6)]
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert not collisions,collisions
assert screen_lidar_gap>=1.4 and screen_perf_gap>=10
assert optical_z-screen_top>5 and pcb_z-ch-ZT>=2.9
doc.saveAs(str(HERE/'EdgeMind_Chassis.FCStd'))
App.closeDocument(doc.Name);App.closeDocument(old.Name)
print(json.dumps({'parts':len(items),'screen_lidar_gap_mm':screen_lidar_gap,'screen_perfboard_gap_mm':screen_perf_gap,'screen_optical_margin_mm':optical_z-screen_top,'wire_openings':len(wire_slots),'critical_interferences':collisions}),flush=True)
