"""Round-trip deliverables, verify source wheel identity and upper-group movement."""
from pathlib import Path
import json
import FreeCAD as App
import Part,Mesh

HERE=Path(__file__).resolve().parent
report=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
ref=json.loads((HERE/'reference-extraction.json').read_text(encoding='utf-8'))
def bounds(s):
    b=s.optimalBoundingBox(False,False)
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
print('Reopen native assembly and check independent upper assembly',flush=True)
doc=App.openDocument(str(HERE/'EdgeMind_Chassis.FCStd'))
objects={o.Name:o for o in doc.Objects if o.TypeId=='Part::Feature'}
assert len(objects)==len(report['parts'])
for p in report['parts']:
    o=objects[p['name']]
    assert not o.Shape.isNull() and o.Shape.isClosed(),p['name']
    assert max(abs(a-b) for a,b in zip(bounds(o.Shape),p['bounds']))<.01,p['name']
u=doc.getObject('UpperAssembly')
upper_parts=[p['name'] for p in report['parts'] if p['upper_assembly']]
assert {o.Name for o in u.Group}==set(upper_parts)
initial={n:objects[n].getGlobalPlacement().Base.z for n in upper_parts}
u.Placement.Base=App.Vector(0,0,65);doc.recompute()
assert all(abs(objects[n].getGlobalPlacement().Base.z-initial[n]-65)<1e-6 for n in upper_parts)
u.Placement.Base=App.Vector(0,0,0);doc.recompute()
report['fcstd_reopened']=True;report['native_objects_closed']=len(objects)
report['upper_assembly_verified']={'members':len(upper_parts),'group_lift_mm':65,'all_members_move_together':True}

print('Read STEP exports and compare precise bounds, topology and shell volume',flush=True)
report['step_roundtrip']={}
for filename,collection in [('EdgeMind_Assembly.step',[o.Shape for o in objects.values()]),
   ('EdgeMind_Shell.step',[objects[p['name']].Shape for p in report['parts'] if p['category'] in ('Shell','Mounts') and p['role']=='designed'])]:
    before=Part.makeCompound(collection);after=Part.read(str(HERE/filename))
    assert len(after.Solids)==len(before.Solids),(filename,len(after.Solids),len(before.Solids))
    bb,ba=bounds(before),bounds(after)
    delta=max(abs(a-b) for a,b in zip(bb,ba));assert delta<.01,(filename,delta)
    assert after.isClosed(),filename
    valid=after.isValid();assert valid,filename
    entry={'solids':len(after.Solids),'closed':True,'valid':True,'maximum_bound_delta_mm':delta}
    if filename=='EdgeMind_Shell.step':
        vd=abs(after.Volume-before.Volume);assert vd<.05,vd
        entry['volume_delta_mm3']=vd
    report['step_roundtrip'][filename]=entry

report['source_geometry_identity']={}
for p in ref['parts']:
    o=objects[p['name']]
    assert len(o.Shape.Faces)==p['faces'],p['name']
    assert max(abs(a-b) for a,b in zip(bounds(o.Shape),p['bounds']))<.001,p['name']
    report['source_geometry_identity'][p['name']]={'source_solid_index':p['source_solid_index'],'faces_match':True,'bounds_match':True,'scale':1}
report['stl_files']={}
for p in sorted((HERE/'parts-stl').glob('*.stl')):
    m=Mesh.Mesh(str(p));assert m.isSolid(),p.name
    report['stl_files'][p.name]={'closed':True,'facets':m.CountFacets}
assert len(report['stl_files'])==sum(p['export_part'] for p in report['parts'])
assert report['battery_fence']['floor_thickness_mm']==4 and not report['battery_fence']['recess_cut']
assert report['battery_fence']['cable_tie_slots']==4
assert max(abs(z) for z in report['four_wheel_ground_z'])<.001
assert not report['critical_interferences']
exp=App.openDocument(str(HERE/'EdgeMind_Exploded.FCStd'))
assert abs(exp.getObject('UpperAssembly').Placement.Base.z-65)<1e-8
report['exploded_native_verified']=True
App.closeDocument(exp.Name);App.closeDocument(doc.Name)
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'native_parts':len(objects),'STEP':report['step_roundtrip'],'closed_STL':len(report['stl_files']),
 'upper_members':len(upper_parts),'original_R3X_parts':len(ref['parts']),'ground_z':report['four_wheel_ground_z'],
 'base_difference_mm3':report['solidcraft_exact_difference_mm3'],'interferences':len(report['critical_interferences'])},ensure_ascii=False),flush=True)
