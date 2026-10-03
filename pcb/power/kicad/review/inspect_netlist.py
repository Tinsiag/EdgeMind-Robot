from kicad_tools import *
import xml.etree.ElementTree as ET
import sys

tag = sys.argv[1] if len(sys.argv)>1 else 'before'
xml = ET.parse(ROOT / 'review' / (tag+'.net.xml')).getroot()
pin_nets = {}
for net in xml.findall('./nets/net'):
    for node in net.findall('node'):
        pin_nets[(node.attrib['ref'],node.attrib['pin'])] = net.attrib['name']
print('NETLIST COMPONENTS')
for comp in xml.findall('./components/comp'):
    ref = comp.attrib['ref']
    if ref.startswith('#') or ref=='?':
        continue
    print(ref,comp.findtext('value'),comp.findtext('footprint'),comp.findtext('tstamps'),[(p,n) for (r,p),n in pin_nets.items() if r==ref])
print('IMPORT FIELDS')
st,sch=load('.kicad_sch')
for s in children(sch,'symbol'):
    if prop(s,'Reference') in ['U1','U5','D1','C58','L1','USB1','SW2']:
        print(prop(s,'Reference'),[(str(p[1]),str(p[2])) for p in children(s,'property')], 'id',val(s,'lib_id'))
bt,pcb=load('.kicad_pcb')
for fp in children(pcb,'footprint'):
    if prop(fp,'Reference') in ['U1','R1','C6','USB1','U2','']:
        print('PAD TYPE',prop(fp,'Reference'),val(fp,'attr'),[(str(p[1]),str(p[2]),child(p,'drill'),child(p,'layers')) for p in children(fp,'pad')])
print('SCHEMATIC TEXTS',[(str(x[1]),child(x,'at')) for x in children(sch,'text')])
for f in ['before-drc.json','before-erc.json']:
    d=json.loads((ROOT/'review'/f).read_text(encoding='utf-8'))
    vals=d.get('violations',[]) if 'drc' in f else [v for s in d['sheets'] for v in s['violations']]
    for v in vals:
        if v['type'] in ['shorting_items','unconnected_wire_endpoint','lib_symbol_mismatch','courtyards_overlap']:
            print(v['type'],v['description'],[i['description'] for i in v['items']])
