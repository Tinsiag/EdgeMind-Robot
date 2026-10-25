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
Part.export([p['object'] for p in items],str(HERE/'EdgeMind_Assembly.step'))
plate=doc.getObject('ThirdDeck').Shape.copy();plate.translate(App.Vector(0,0,-report['third_deck_bottom_z']))
mesh=MeshPart.meshFromShape(Shape=plate,LinearDeflection=.10,AngularDeflection=.15,Relative=False)
assert mesh.isSolid();mesh.write(str(HERE/'ThirdDeck.stl'))
print('Reuse V3 geometry meshes and tessellate the new sensor layer',flush=True)
previous={p['name']:p for p in json.loads((HERE.parent/'v3-camera-closed-rails/preview-meshes.json').read_text(encoding='utf-8'))}
data=[]
for p in items:
    if p['reuse_previous_mesh']:
        vertices=previous[p['name']]['vertices'];faces=previous[p['name']]['indices']
    else:
        v,f=p['object'].Shape.tessellate(.20)
        vertices=[[round(c,5) for c in a] for a in v];faces=[list(a) for a in f]
    data.append({k:p[k] for k in ('name','label','category','color','layer','upper_assembly','third_assembly')}|
                {'vertices':vertices,'indices':faces})
(HERE/'preview-meshes.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
doc.getObject('UpperAssembly').Placement.Base=App.Vector(0,0,50)
doc.getObject('ThirdAssembly').Placement.Base=App.Vector(0,0,120)
doc.recompute();doc.saveAs(str(HERE/'EdgeMind_Exploded.FCStd'));App.closeDocument(doc.Name)
# Add standard headless FreeCAD view providers for meaningful colors on opening.
for filename in ('EdgeMind_Chassis.FCStd','EdgeMind_Exploded.FCStd'):
    path=HERE/filename;gui=ET.Element('Document',{'SchemaVersion':'1','HasExpansion':'1'})
    providers=ET.SubElement(gui,'ViewProviderData',{'Count':str(len(items))})
    for p in items:
        vp=ET.SubElement(providers,'ViewProvider',{'name':p['name'],'expanded':'0'})
        props=ET.SubElement(vp,'Properties',{'Count':'4'})
        for name,typ,val in [('ShapeColor','App::PropertyColor',p['color']),('LineColor','App::PropertyColor',(.1,.12,.14)),('Visibility','App::PropertyBool',True),('DisplayMode','App::PropertyEnumeration',0)]:
            prop=ET.SubElement(props,'Property',{'name':name,'type':typ})
            if typ=='App::PropertyColor':ET.SubElement(prop,'PropertyColor',{'value':str((round(val[0]*255)<<24)|(round(val[1]*255)<<16)|(round(val[2]*255)<<8)|255)})
            elif typ=='App::PropertyBool':ET.SubElement(prop,'Bool',{'value':'true'})
            else:ET.SubElement(prop,'Integer',{'value':'0'})
    tmp=path.with_suffix('.export.FCStd')
    with zipfile.ZipFile(path) as src,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename!='GuiDocument.xml':dst.writestr(info,src.read(info.filename))
        dst.writestr('GuiDocument.xml',ET.tostring(gui,encoding='utf-8',xml_declaration=True))
    tmp.replace(path)
print(json.dumps({'parts':len(items),'third_layer_parts':len(third),'plate_closed_stl':True}),flush=True)
