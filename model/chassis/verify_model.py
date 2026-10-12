from pathlib import Path
import json
import FreeCAD as App
import Part
import Mesh

OUT=Path(__file__).resolve().parent/'v1-fixed-front-wheels'
report=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
doc=App.openDocument(str(OUT/'EdgeMind_Chassis.FCStd'))
objects={o.Name:o for o in doc.Objects if o.TypeId=='Part::Feature'}
assert len(objects)==len(report['parts'])
for obj in objects.values():
    assert obj.Shape.isValid() and obj.Shape.Volume>0,obj.Name
report['fcstd_reopened']=True
report['native_objects_valid']=len(objects)
report['step_roundtrip']={}
for filename,collection in [('EdgeMind_Shell.step',[objects[p['name']].Shape for p in report['parts']
                                                  if p['category'] in ('Shell','Mounts') and p['role']=='designed']),
                            ('EdgeMind_Assembly.step',[o.Shape for o in objects.values()])]:
    original=Part.makeCompound(collection)
    imported=Part.read(str(OUT/filename))
    assert imported.isValid()
    assert len(imported.Solids)==len(original.Solids)
    eb,ob=imported.optimalBoundingBox(False,False),original.optimalBoundingBox(False,False)
    va=[eb.XMin,eb.YMin,eb.ZMin,eb.XMax,eb.YMax,eb.ZMax]
    vb=[ob.XMin,ob.YMin,ob.ZMin,ob.XMax,ob.YMax,ob.ZMax]
    delta=max(abs(a-b) for a,b in zip(va,vb))
    assert delta<.01,(filename,va,vb)
    volume_delta=abs(imported.Volume-original.Volume)/original.Volume
    assert volume_delta<1e-5,(filename,volume_delta)
    report['step_roundtrip'][filename]={'valid':True,'solids':len(imported.Solids),'bounds_match':True,
                                       'maximum_bound_delta_mm':delta,'relative_volume_delta':volume_delta}
report['stl_files']={}
for path in sorted((OUT/'parts-stl').glob('*.stl')):
    mesh=Mesh.Mesh(str(path))
    assert mesh.isSolid(),path.name
    report['stl_files'][path.name]={'closed':True,'facets':mesh.CountFacets}
assert len(report['stl_files'])==len(list((OUT/'parts-step').glob('*.step')))
report['exported_part_count']=len(report['stl_files'])
assert not report['critical_interferences']
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'native_objects':len(objects),'size_mm':report['assembly_size_mm'],
                  'step_roundtrip':report['step_roundtrip'],'closed_stl_count':report['exported_part_count'],
                  'key_interferences':len(report['critical_interferences']),'ground_z':report['four_wheel_ground_z']},ensure_ascii=False),flush=True)
