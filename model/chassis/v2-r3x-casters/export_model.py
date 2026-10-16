"""Export a verified native assembly without rebuilding the source geometry."""
from pathlib import Path
import json,zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part,MeshPart

HERE=Path(__file__).resolve().parent
def export():
    report=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    native=HERE/'EdgeMind_Chassis.FCStd'
    # Resume an interrupted first export; subsequent builds keep colours in the report.
    saved_colors={}
    styled=HERE/'EdgeMind_Chassis.styled.FCStd'
    if styled.exists():
        with zipfile.ZipFile(styled) as z:
            xml=ET.fromstring(z.read('GuiDocument.xml'))
            for vp in xml.findall('./ViewProviderData/ViewProvider'):
                c=vp.find('./Properties/Property[@name="ShapeColor"]/PropertyColor')
                if c is not None:
                    v=int(c.get('value'));saved_colors[vp.get('name')]=[(v>>shift&255)/255 for shift in (24,16,8)]
    doc=App.openDocument(str(native));items=[]
    for p in report['parts']:
        o=doc.getObject(p['name']);assert o is not None,p['name']
        p['color']=p.get('color',saved_colors.get(p['name'],[.62,.67,.72]))
        items.append(dict(p,object=o))
    upper=doc.getObject('UpperAssembly');assert abs(upper.Placement.Base.z)<1e-8
    print('Export full STEP, shell STEP and exact hardware for SolidCraft',flush=True)
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
    print('Tessellate source geometry for offline preview',flush=True)
    mesh_data=[]
    for i in items:
        v,f=i['object'].Shape.tessellate(.5)
        mesh_data.append({'name':i['name'],'label':i['label'],'category':i['category'],'color':i['color'],
            'upper_assembly':i['upper_assembly'],'vertices':[[round(p.x,4),round(p.y,4),round(p.z,4)] for p in v],
            'indices':[list(t) for t in f]})
    (HERE/'preview-meshes.json').write_text(json.dumps(mesh_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    upper.Placement.Base=App.Vector(0,0,65);doc.recompute()
    doc.saveAs(str(HERE/'EdgeMind_Exploded.FCStd'))
    App.closeDocument(doc.Name)
    for path in [native,HERE/'EdgeMind_Exploded.FCStd']:
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
        tmp=path.with_suffix('.export.FCStd')
        with zipfile.ZipFile(path) as src,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                if info.filename!='GuiDocument.xml':dst.writestr(info,src.read(info.filename))
            dst.writestr('GuiDocument.xml',ET.tostring(gui,encoding='utf-8',xml_declaration=True))
        tmp.replace(path)
    (HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'exported_parts':len(items),'STL_parts':sum(i['export_part'] for i in items)}),flush=True)
if __name__=='__main__':export()
