"""Readback/clearance checks for the V5 portrait screen and rotated source board."""
from pathlib import Path
import json
import FreeCAD as App
import Part,Mesh
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'));p=r['parameters'];V=App.Vector
d=App.openDocument(str(HERE/'EdgeMind_Chassis.FCStd'))
plate=d.getObject('ThirdDeck').Shape;z=r['third_deck_bottom_z'];t=5
assert plate.isValid() and plate.isClosed() and len(plate.Solids)==1
assert abs(plate.BoundBox.ZLength-5)<1e-7
mounts=p['third_support_holes_xy']+r['lidar']['mount_holes_xy']+r['imu']['mount_holes_xy_reference']+r['perfboard']['mount_holes_xy']+r['screen']['module_mount_holes_xy_reference']
def capsule(x,y,w,l):
    radius=w/2;straight=(l-w)/2
    return Part.makeBox(w,2*straight,t,V(x-radius,y-straight,z)).fuse(Part.makeCylinder(radius,t,V(x,y-straight,z))).fuse(Part.makeCylinder(radius,t,V(x,y+straight,z))).removeSplitter()
mount_cutouts=[Part.makeCylinder(1.7,t,V(x,y,z)) for x,y in p['third_support_holes_xy']]
mount_cutouts += [Part.makeCylinder(1.15,t,V(x,y,z)) for x,y in r['lidar']['mount_holes_xy']]
mount_cutouts += [capsule(x,y,*p['imu_plate_mount_slot_size_xy']) for x,y in r['imu']['mount_holes_xy_reference']]
mount_cutouts += [Part.makeCylinder(1.4,t,V(x,y,z)) for x,y in r['perfboard']['mount_holes_xy']]
mount_cutouts += [capsule(x,y,*p['screen_plate_mount_slot_xy']) for x,y in r['screen']['module_mount_holes_xy_reference']]
for x,y in mounts:
    assert plate.common(Part.makeCylinder(.9,7,V(x,y,z-1))).Volume<1e-7,(x,y)
def slot_shape(s):
    x,y,w,l,rad=s
    pieces=[Part.makeBox(w-2*rad,l,t,V(x-w/2+rad,y-l/2,z)),Part.makeBox(w,l-2*rad,t,V(x-w/2,y-l/2+rad,z))]
    pieces += [Part.makeCylinder(rad,t,V(x+dx*(w/2-rad),y+dy*(l/2-rad),z)) for dx in (-1,1) for dy in (-1,1)]
    a=pieces[0]
    for b in pieces[1:]:a=a.fuse(b)
    return a.removeSplitter()
slots=[slot_shape(s) for s in r['wire_slots']+r['vent_slots']]
assert len(r['wire_slots'])==11
min_web=1e9
for i,a in enumerate(slots[:len(r['wire_slots'])]):
    assert plate.common(a).Volume<1e-6
    for j,b in enumerate(slots):
        if i==j:continue
        gap=a.distToShape(b)[0];assert gap>=4-1e-6,(i,j,gap);min_web=min(min_web,gap)
    for j,b in enumerate(mount_cutouts):
        gap=a.distToShape(b)[0]
        assert gap>=4-1e-6,(i,j,gap)
screen_pcb=d.getObject('ScreenPCB').Shape;screen_bb=screen_pcb.BoundBox
assert abs(screen_bb.XLength-67.2)<1e-6 and abs(screen_bb.YLength-116)<1e-6
assert abs(screen_bb.XMin+88)<1e-6
assert screen_bb.XMax<0
perf=d.getObject('PerfboardSource').Shape;pb=perf.BoundBox
raw=Part.read(str(HERE/'references/3D_PCB2_2026-10-20.step'))
assert len(perf.Faces)==len(raw.Faces) and abs(perf.Volume-raw.Volume)<1e-6
assert abs(pb.XLength-r['perfboard']['source_size_mm'][1])<1e-6
assert abs(pb.YLength-r['perfboard']['source_size_mm'][0])<1e-6
assert abs((pb.XMin+pb.XMax)/2-37)<1e-6 and abs((pb.YMin+pb.YMax)/2+20)<1e-6
r['perfboard']['lidar_to_board_edge_gap_mm']=pb.YMin-d.getObject('LidarSource0').Shape.BoundBox.YMax
screen_shapes=[d.getObject(i['name']).Shape for i in r['parts'] if i['name'].startswith('Screen')]
screen=Part.makeCompound(screen_shapes)
lidar=d.getObject('LidarSource0').Shape
assert screen.distToShape(lidar)[0]>=1.4
assert screen.distToShape(perf)[0]>=10
optical_z=r['lidar']['base_z']+20.7
assert optical_z-screen.BoundBox.ZMax>5
assert abs(d.getObject('ScreenBackInterface').Shape.BoundBox.ZMin-plate.BoundBox.ZMax-3)<1e-6
assert abs(d.getObject('ScreenLCDFrame').Shape.BoundBox.ZLength-4.05)<1e-6
assert abs(d.getObject('ScreenActiveGlass').Shape.BoundBox.XLength-53.856)<1e-6
assert abs(d.getObject('ScreenActiveGlass').Shape.BoundBox.YLength-95.04)<1e-6
top=d.getObject('ThirdAssembly');assert {o.Name for o in top.Group}=={i['name'] for i in r['parts'] if i['layer']==3}
before=d.getObject('ScreenPCB').getGlobalPlacement().Base.z
top.Placement.Base=V(0,0,120);d.recompute()
assert abs(d.getObject('ScreenPCB').getGlobalPlacement().Base.z-before-120)<1e-7
top.Placement.Base=V(0,0,0);d.recompute()
print('Read back modified plate, screen and third-layer STEP exports',flush=True)
r['step_roundtrip']={}
for filename,objects in [('ThirdDeck.step',[d.getObject('ThirdDeck')]),('EdgeMind_ScreenAssembly.step',[d.getObject(i['name']) for i in r['parts'] if i['name'].startswith('Screen')]),('EdgeMind_ThirdAssembly.step',list(top.Group)),('EdgeMind_Assembly.step',[d.getObject(i['name']) for i in r['parts']])]:
    original=Part.makeCompound([o.Shape for o in objects]);after=Part.read(str(HERE/filename))
    assert after.isClosed() and len(after.Solids)==len(original.Solids),filename
    assert all(len(a.Faces)==len(b.Faces) for a,b in zip(original.Solids,after.Solids)),filename
    delta=0
    for a,b in zip(original.Solids,after.Solids):
        ba,bb=a.BoundBox,b.BoundBox
        delta=max(delta,*[abs(getattr(ba,k)-getattr(bb,k)) for k in ('XMin','YMin','ZMin','XMax','YMax','ZMax')])
    assert delta<.01,(filename,delta)
    entry={'closed':True,'solids':len(after.Solids),'face_counts_match':True,'bounds_delta_mm':delta}
    if filename!='EdgeMind_Assembly.step':
        assert after.isValid(),filename
        volume_delta=abs(after.Volume-original.Volume);assert volume_delta<.1,(filename,volume_delta)
        entry.update(valid=True,volume_delta_mm3=volume_delta)
    else:entry['verification_scope']='Full export topology/bounds; changed third layer validity/volume checked separately. Unchanged V4 wheel geometry reused.'
    r['step_roundtrip'][filename]=entry;print(json.dumps({'file':filename,**entry}),flush=True)
mesh=Mesh.Mesh(str(HERE/'ThirdDeck.stl'));assert mesh.isSolid()
assert abs(mesh.BoundBox.ZMin)<1e-5 and abs(mesh.BoundBox.ZMax-5)<1e-5
assert not r['critical_interferences']
r.update(readback_verified=True,third_assembly_moves_independently=True,plate_stl={'closed':True,'facets':mesh.CountFacets,'bottom_z':mesh.BoundBox.ZMin},
 wire_openings={'total':len(r['wire_slots']),'minimum_web_mm':min_web,'mount_keepouts_clear':True},
 feature_checks={'plate_mount_holes_checked':len(mounts),'screen_portrait':True,'perfboard_rotated_90_degrees':True,'screen_left_perfboard_right':True,'screen_back_interface_clearance_mm':3,'screen_below_scan_zone':True})
(HERE/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
App.closeDocument(d.Name)
print(json.dumps({'parts':len(r['parts']),'mount_points_checked':len(mounts),'wire_openings':len(r['wire_slots']),'minimum_wire_web_mm':min_web,'screen_gap_mm':r['screen']['screen_lidar_gap_mm'],'source_perfboard_rigid_transform':True}),flush=True)
