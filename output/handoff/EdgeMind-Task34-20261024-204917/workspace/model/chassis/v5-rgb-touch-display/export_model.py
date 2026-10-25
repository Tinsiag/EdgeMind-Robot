"""Export native CAD, exact STEP and preview tessellation; preserve source meshes."""
from pathlib import Path
import json, zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part, MeshPart
HERE=Path(__file__).resolve().parent
report=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
doc=App.openDocument(str(HERE/'EdgeMind_Chassis.FCStd'))
items=[dict(p,object=doc.getObject(p['name'])) for p in report['parts']]
third=[p['object'] for p in items if p['third_assembly']]
print('Export third layer, plate and complete assembly STEP',flush=True)
Part.export(third,str(HERE/'EdgeMind_ThirdAssembly.step'))
Part.export([doc.getObject('ThirdDeck')],str(HERE/'ThirdDeck.step'))
Part.export([i['object'] for i in items if i['name'].startswith('Screen')],str(HERE/'EdgeMind_ScreenAssembly.step'))
Part.export([p['object'] for p in items],str(HERE/'EdgeMind_Assembly.step'))
plate=doc.getObject('ThirdDeck').Shape.copy();plate.translate(App.Vector(0,0,-report['third_deck_bottom_z']))
mesh=MeshPart.meshFromShape(Shape=plate,LinearDeflection=.10,AngularDeflection=.15,Relative=False)
assert mesh.isSolid();mesh.write(str(HERE/'ThirdDeck.stl'))
print('Reuse/rotate V4 geometry meshes and tessellate new plate and screen reference',flush=True)
previous={p['name']:p for p in json.loads((HERE.parent/report['mesh_cache_directory']/'preview-meshes.json').read_text(encoding='utf-8'))}
data=[]
for p in items:
    if p['reuse_previous_mesh']:
        vertices=previous[p['name']]['vertices'];faces=previous[p['name']]['indices']
        if p.get('mesh_rotation_z'):
            assert p['mesh_rotation_z']==90
            dx,dy,dz=p['mesh_translation']
            vertices=[[round(-v[1]+dx,5),round(v[0]+dy,5),round(v[2]+dz,5)] for v in vertices]
    else:
        v,f=p['object'].Shape.tessellate(.20)
        vertices=[[round(c,5) for c in a] for a in v];faces=[list(a) for a in f]
    data.append({k:p[k] for k in ('name','label','category','color','layer','upper_assembly','third_assembly')}|
                {'vertices':vertices,'indices':faces})
(HERE/'preview-meshes.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
doc.getObject('UpperAssembly').Placement.Base=App.Vector(0,0,50)
doc.getObject('ThirdAssembly').Placement.Base=App.Vector(0,0,120)
doc.recompute();doc.saveAs(str(HERE/'EdgeMind_Exploded.FCStd'));App.closeDocument(doc.Name)
print(json.dumps({'parts':len(items),'third_layer_parts':len(third),'plate_closed_stl':True}),flush=True)
