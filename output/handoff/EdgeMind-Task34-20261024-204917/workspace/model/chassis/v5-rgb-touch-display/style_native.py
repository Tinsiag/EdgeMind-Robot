"""Apply colors in a fresh process after FreeCAD releases its archive handles."""
from pathlib import Path
import json,zipfile,time
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
items=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))['parts']
for name in ('EdgeMind_Chassis.FCStd','EdgeMind_Exploded.FCStd'):
    path=HERE/name;tmp=path.with_suffix('.export.FCStd')
    gui=ET.Element('Document',{'SchemaVersion':'1','HasExpansion':'1'})
    providers=ET.SubElement(gui,'ViewProviderData',{'Count':str(len(items))})
    for p in items:
        vp=ET.SubElement(providers,'ViewProvider',{'name':p['name'],'expanded':'0'})
        props=ET.SubElement(vp,'Properties',{'Count':'4'})
        for field,typ,val in [('ShapeColor','App::PropertyColor',p['color']),('LineColor','App::PropertyColor',(.1,.12,.14)),('Visibility','App::PropertyBool',True),('DisplayMode','App::PropertyEnumeration',0)]:
            prop=ET.SubElement(props,'Property',{'name':field,'type':typ})
            if typ=='App::PropertyColor':ET.SubElement(prop,'PropertyColor',{'value':str((round(val[0]*255)<<24)|(round(val[1]*255)<<16)|(round(val[2]*255)<<8)|255)})
            elif typ=='App::PropertyBool':ET.SubElement(prop,'Bool',{'value':'true'})
            else:ET.SubElement(prop,'Integer',{'value':'0'})
    with zipfile.ZipFile(path) as src,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename!='GuiDocument.xml':dst.writestr(info,src.read(info.filename))
        dst.writestr('GuiDocument.xml',ET.tostring(gui,encoding='utf-8',xml_declaration=True))
    for attempt in range(8):
        try:tmp.replace(path);break
        except PermissionError:
            if attempt==7:raise
            time.sleep(.25*(attempt+1))
print('V5 native colors applied')
