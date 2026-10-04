from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET
import pcbnew
from kicad_tools import parse, children, prop
R=Path(__file__).resolve().parents[1]
X=ET.parse(R/'review/all-layout-current.net.xml').getroot()
N={(n.get('ref'),n.get('pin')):net.get('name') for net in X.findall('nets/net') for n in net.findall('node')}
C={c.get('ref'):c for c in X.findall('components/comp')}
B=pcbnew.LoadBoard(str(R/'ProPrj_power_2026-10-02.kicad_pcb'))
F={f.GetReference():f for f in B.GetFootprints()}
D={'sheets':{},'parts':{},'edge':[], 'layers':B.GetCopperLayerCount(),'tracks':len(list(B.GetTracks())),'zones':len(list(B.Zones())), 'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*R.glob('*.kicad_sch'),*R.glob('*.kicad_pcb')]}}
for s in sorted(R.glob('[0-9][0-9]_*.kicad_sch')):
 refs=sorted({prop(c,'Reference') for c in children(parse(s.read_text(encoding='utf-8')),'symbol') if not prop(c,'Reference').startswith('#')})
 D['sheets'][s.stem]=refs
 print('\n'+s.stem+' '+str(len(refs)))
 for r in refs:
  c=C[r]; f=F[r]
  pins={p.GetNumber():p.GetNetname() for p in f.Pads() if p.GetNumber()}
  assert all(n==N[r,p] for p,n in pins.items()),r
  D['parts'][r]={'value':c.findtext('value'),'footprint':c.findtext('footprint'),'position':[pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)],'angle':f.GetOrientationDegrees(),'pins':pins}
  print(r,c.findtext('value'),' | ', ' '.join(p+':'+n for p,n in pins.items()))
for d in B.GetDrawings():
 if d.GetLayer()==pcbnew.Edge_Cuts:
  D['edge'].append({'shape':str(d.GetShape()),'start':[pcbnew.ToMM(d.GetStart().x),pcbnew.ToMM(d.GetStart().y)],'end':[pcbnew.ToMM(d.GetEnd().x),pcbnew.ToMM(d.GetEnd().y)]})
assert set(D['parts'])==set(F),(set(F)-set(D['parts']))
(R/'review/all-layout-current.json').write_text(json.dumps(D,ensure_ascii=False,indent=2),encoding='utf-8')
print('\nPCB:',len(F),'parts;',D['layers'],'layers;',D['tracks'],'tracks;',D['zones'],'zones; edges',D['edge'])
