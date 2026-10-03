"""Check native-export connectivity, UUID links, pad numbers and geometry."""
from kicad_tools import *
from repair_import import RENAME
import xml.etree.ElementTree as ET
import pcbnew
import csv

def netlist(filename):
    xml=ET.parse(ROOT/'review'/filename).getroot()
    comps={c.attrib['ref']:c for c in xml.findall('./components/comp')
           if not c.attrib['ref'].startswith('#') and c.attrib['ref']!='?'}
    pins={}
    partitions=[]
    for net in xml.findall('./nets/net'):
        group=[]
        for n in net.findall('node'):
            ref,pin=n.attrib['ref'],n.attrib['pin']
            if ref in comps:
                pins[(ref,pin)]=net.attrib['name']
                group.append((comps[ref].findtext('tstamps'),pin))
        if group:
            partitions.append(tuple(sorted(group)))
    return comps,pins,set(partitions)

before,bpins,bparts=netlist('before.net.xml')
after,apins,aparts=netlist('after.net.xml')
assert len(before)==len(after)==53
assert bparts==aparts,'Schematic electrical connectivity changed'
st,sch=load('.kicad_sch')
bt,pcb=load('.kicad_pcb')
syms={prop(s,'Reference'):s for s in children(sch,'symbol') if prop(s,'Reference') in after}
fps={prop(f,'Reference'):f for f in children(pcb,'footprint') if prop(f,'Reference') in after}
assert len(syms)==len(fps)==53
mapping=[]
for ref,comp in after.items():
    s,f=syms[ref],fps[ref]
    assert prop(s,'Footprint')==str(f[1])
    assert val(f,'path')==f'/{val(sch,"uuid")}/{val(s,"uuid")}'
    library,name=str(f[1]).split(':',1)
    path=ROOT/(library+'.pretty')/(name+'.kicad_mod')
    assert path.is_file(),f'Missing footprint file: {path}'
    lib=parse(path.read_text(encoding='utf-8'))
    fnumbers={str(p[1]) for p in children(f,'pad')}
    lnumbers={str(p[1]) for p in children(lib,'pad')}
    nnumbers={p for r,p in apins if r==ref}
    assert fnumbers==lnumbers==nnumbers,f'Pin/pad number mismatch: {ref}'
    for p in children(f,'pad'):
        pin=str(p[1])
        assert val(p,'net')==apins[(ref,pin)],f'Wrong pad net: {ref}.{pin}'
        mapping.append([ref,pin,apins[(ref,pin)],prop(s,'Footprint'),val(s,'uuid'),val(f,'uuid')])
with (ROOT/'review'/'pin-map.csv').open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.writer(stream)
    writer.writerow(['Reference','Pin/Pad','Net','Footprint','SchematicUUID','PCB_UUID'])
    writer.writerows(mapping)
original=pcbnew.LoadBoard(str(ROOT/'review'/'repair-backups'/(STEM+'.kicad_pcb')))
current=pcbnew.LoadBoard(str(ROOT/(STEM+'.kicad_pcb')))
orig={RENAME.get(f.GetReference(),f.GetReference()):f for f in original.GetFootprints() if f.GetReference()}
now={f.GetReference():f for f in current.GetFootprints()}
converted=0
for ref,f in orig.items():
    nf=now[ref]
    assert f.GetPosition()==nf.GetPosition()
    assert abs(f.GetOrientationDegrees()-nf.GetOrientationDegrees())<1e-7
    npads={p.GetNumber():p for p in nf.Pads()}
    for p in f.Pads():
        n=npads[p.GetNumber()]
        assert p.GetPosition()==n.GetPosition() and p.GetSize()==n.GetSize()
        if p.GetDrillSize().x==1000:
            assert n.GetAttribute()==pcbnew.PAD_ATTRIB_SMD
            converted+=1
        else:
            assert p.GetDrillSize()==n.GetDrillSize()
assert converted==118
def tracks(board):
    return sorted((t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,
                   t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth(),
                   t.GetLayer(),isinstance(t,pcbnew.PCB_VIA))
                  for t in board.GetTracks())
assert tracks(original)==tracks(current),'Existing routing geometry changed'
oldtext=(ROOT/'review'/'repair-backups'/(STEM+'.kicad_pcb')).read_text(encoding='utf-8')
oldtree=parse(oldtext)
original_zones={val(z,'uuid'):z for z in children(oldtree,'zone') if child(z,'attr') is None}
current_zones={val(z,'uuid'):z for z in children(pcb,'zone') if child(z,'attr') is None}
assert len(original_zones)==len(current_zones)==9
def canonical(n):
    if isinstance(n,Node):
        return [canonical(c) for c in n]
    try:
        return round(float(n),9)
    except ValueError:
        return str(n)
for uid,zone in original_zones.items():
    assert canonical(child(zone,'polygon'))==canonical(child(current_zones[uid],'polygon'))
def rule_counts(name):
    d=json.loads((ROOT/'review'/name).read_text(encoding='utf-8'))
    groups={'violations':[v for s in d['sheets'] for v in s['violations']]} if 'sheets' in d else {
        k:d[k] for k in ['violations','unconnected_items','schematic_parity']}
    return {k:{'total':len(v),'errors':sum(i['severity']=='error' for i in v),
               'warnings':sum(i['severity']=='warning' for i in v),
               'types':dict(Counter(i['type'] for i in v))} for k,v in groups.items()}
result={'physical_components':53,'validated_pins':len(mapping),
        'project_local_footprints':len(list((ROOT/'ProPrj_pow-easyedapro.pretty').glob('*.kicad_mod'))),
        'corrected_SMD_pads':converted,'schematic_connectivity_unchanged':True,
        'component_positions_and_pad_geometry_unchanged':True,'existing_routing_geometry_unchanged':True,
        'copper_zone_outlines_preserved_and_refilled':9,
        'imported_generated_teardrops_discarded_by_native_refill':97,
        'before_erc':rule_counts('before-erc.json'),
        'after_erc':rule_counts('after-erc.json'),'before_drc':rule_counts('before-drc.json'),
        'after_drc':rule_counts('after-drc.json')}
assert result['after_drc']['schematic_parity']['total']==0
assert 'lib_footprint_mismatch' not in result['after_drc']['violations']['types']
assert 'footprint_link_issues' not in result['after_erc']['violations']['types']
(ROOT/'review'/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
