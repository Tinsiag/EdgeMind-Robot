"""Audit physical netlist selectors; this does not replace the tool's STA."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
PROJECT=REPO/'code/camera-car-control/a745-autonomous'
BUILD=PROJECT/'.local/gowin-a745-autonomous'
netlist=(BUILD/'impl/gwsynthesis/a745.vg').read_text(encoding='utf-8')
cells={}
vendor=PROJECT/'vendor/reference/board-60b-ddr3-memory-interface.vo'
vendor_sha=hashlib.sha256(vendor.read_bytes()).hexdigest()
assert vendor_sha=='c9da2a7b0f89226a6063b3d57037f6ed3d36ca2a0914de2eaefe7bf22a119cbd'
# The synthesis .vg retains the encrypted IP. Its matching board-supplied
# plaintext simulation model supplies the internal names, while the final
# tool constraint report must independently confirm each constraint active.
for text,prefix in ((netlist,''),(vendor.read_text(encoding='utf-8'),'memory/')):
    for kind,name,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\(\s*(.*?)\);',text,re.S):
        name=prefix+name.lstrip('\\')
        pins=dict(re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S))
        cells[name]=(kind,pins)
physical=BUILD/'impl/pnr/a745.vo'
result=json.loads((BUILD/'result.json').read_text())
physical_current=physical.is_file() and physical.stat().st_mtime>=result['evidence_freshness_lower_bound_unix'] and result['run_state']!='running'
if physical_current:
    # Use the actual flattened routed netlist when available, not merely the
    # vendor model. Vendor source verification remains an independent check.
    cells={}
    for kind,name,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\(\s*(.*?)\);',physical.read_text(encoding='utf-8'),re.S):
        cells[name.lstrip('\\')]=(kind,dict(re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)))
allpins={name+'/'+pin:(kind,value) for name,(kind,pins) in cells.items() for pin,value in pins.items()}
records=[]
for constraint in (PROJECT/'constraints/ddr_exceptions_reference.sdc').read_text().splitlines():
    if not constraint.startswith('set_'):continue
    matches=[]
    for group in re.findall(r'\[get_pins \{([^}]+)\}\]',constraint):
        pins=[]
        for pattern in group.split():
            regex=re.escape(pattern).replace(r'\*','.*').replace(r'\?','.')
            selected=[p for p in allpins if re.fullmatch(regex,p)]
            assert selected, ('Unmatched selector',pattern)
            pins+=selected
        matches.append([{'pin':p,'type':allpins[p][0],'net':allpins[p][1].strip()} for p in sorted(set(pins))])
    records.append({'constraint':constraint,'groups':matches})
for row in records:
    dest=row['groups'][-1]
    cmd=row['constraint']
    if '/RESET}' in cmd:
        reset_net=cells['memory/gw3_top/u_ddr_phy_top/ddr_rsti_reg_2_s0'][1]['Q'].strip()
        assert len(dest)==62 and all(p['type'] in ('DQS','OSER8','OSER8_MEM','IDES8_MEM') and p['net']==reset_net for p in dest),dest
    if '.rburst_neg' in cmd:
        assert len(dest)==4 and all(p['type'] in ('DFFCE','DFFNCE') for p in dest)
    if '/u_dqs/HOLD}' in cmd:
        assert len(dest)==2 and all(p['type']=='DQS' for p in dest)
    if '/CALIB}' in cmd:
        assert len(dest)==16 and all(p['type']=='IDES8_MEM' for p in dest)
    if 'dll_step_base_' in cmd:
        assert len(dest)==8 and all(p['type']=='DFFCE' for p in dest)
    if 'recalib_s_0' in cmd or 'wloadn_1' in cmd:
        assert len(dest)==1 and dest[0]['type']=='DFFCE'
delays=[]  # A745 has no RGMII RX path by construction.
result={'netlist_sha256':hashlib.sha256((BUILD/'impl/gwsynthesis/a745.vg').read_bytes()).hexdigest(),
        'vendor_internal_model_sha256':vendor_sha,
        'internal_selector_basis':'matching vendor plaintext model; active final tool constraints required separately',
        'routed_netlist_used':physical_current,
        'routed_netlist_sha256':hashlib.sha256(physical.read_bytes()).hexdigest() if physical_current else None,
        'ddr_exception_targets':records,'rx_iodelay64_count':len(delays),
        'hardware_programmed':False}
(OUT/'CONSTRAINT-TARGETS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps([{'groups':[len(g) for g in row['groups']], 'destination_types':dict(Counter(p['type'] for p in row['groups'][-1]))} for row in records],indent=2))
