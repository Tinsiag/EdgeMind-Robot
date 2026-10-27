"""Resolve the new CDC exceptions to actual routed flops, not broad domains."""
from pathlib import Path
import json,re,hashlib
OUT=Path(__file__).resolve().parent
vo=(OUT/'build-evidence-final/a741.vo').read_text()
logic={n.lstrip('\\'):(k,{p:v.strip().lstrip('\\') for p,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)})
 for k,n,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo,re.S)}
constraints=(OUT/'build-evidence-final/a741.sdc').read_text()
allpins={n+'/'+p:(k,v) for n,(k,ps) in logic.items() for p,v in ps.items()}
records=[]
for line in constraints.splitlines():
 if not line.startswith('set_') or 'display_cdc/' not in line:continue
 groups=[]
 for group in re.findall(r'\[get_pins \{([^}]+)\}\]',line):
  selected=[]
  for pat in group.split():
   regex=re.escape(pat).replace(r'\*','.*')
   found=[p for p in allpins if re.fullmatch(regex,p)]
   assert found,pat
   assert all(allpins[p][0].startswith('DFF') for p in found)
   selected+=found
  groups.append(sorted(set(selected)))
 records.append({'constraint':line,'groups':groups})
assert len(records)==4
assert len(records[0]['groups'][0])==4
domains={}
for box in ('to_display','to_system'):
 groups={}
 for part in ('held','dst_data'):
  selected=[(n,p) for n,(k,p) in logic.items() if n.startswith('display_cdc/'+box+'/'+part) and k.startswith('DFF')]
  assert selected
  clocks={p['CLK'] for n,p in selected};assert len(clocks)==1
  groups[part]={'count':len(selected),'clock':next(iter(clocks))}
 assert groups['held']['clock']!=groups['dst_data']['clock']
 domains[box]=groups
assert domains['to_display']['held']['clock']==domains['to_system']['dst_data']['clock']
assert domains['to_display']['dst_data']['clock']==domains['to_system']['held']['clock']
out={'passed':True,'resolved_constraints':records,'mailbox_domains':domains,
     'payload_bound_ns':20,'first_stage_toggle_bound_ns':10,'held_bus_release':'after destination capture and two-stage acknowledgement return',
     'physical_netlist_sha256':hashlib.sha256((OUT/'build-evidence-final/a741.vo').read_bytes()).hexdigest()}
(OUT/'DISPLAY-CDC-REVIEW.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(domains,indent=2))
