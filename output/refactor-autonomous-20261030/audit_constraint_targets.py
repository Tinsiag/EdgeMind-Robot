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
def select_pins(pattern):
    regex=re.escape(pattern).replace(r'\*','.*').replace(r'\?','.')
    return sorted(p for p in allpins if re.fullmatch(regex,p))

tx_q=select_pins('transmitter/*/Q0')
assert len(tx_q)==6 and all(allpins[p][0]=='ODDR' for p in tx_q),tx_q
bundle_source=select_pins('net_fifo/wr_ptr_sync_commit_reg*/Q')
bundle_dest=select_pins('net_fifo/wr_ptr_commit_sync_reg*/D')
assert len(bundle_source)==len(bundle_dest)==12,(bundle_source,bundle_dest)
assert all(allpins[p][0].startswith('DFF') for p in bundle_source+bundle_dest)
normalize=lambda value:re.sub(r'\s+','',value)
assert sorted(normalize(allpins[p][1]) for p in bundle_source)==sorted(normalize(allpins[p][1]) for p in bundle_dest)
# Each side shares a single enable: the source holds the whole pointer until
# acknowledged; the destination samples the whole bus on the synchronized update.
assert all(len({cells[p.rsplit('/',1)[0]][1]['CE'].strip() for p in group})==1 for group in (bundle_source,bundle_dest))
bundled_pointer={'source_q_pins':bundle_source,'destination_d_pins':bundle_dest,
                 'source_q_matches_destination_d':True,'bits':len(bundle_source)}
rx_samples=[name for name,(kind,pins) in cells.items() if kind=='IDDR' and name.startswith('receiver/')]
assert cells['tx_divider'][0]=='CLKDIV'
assert cells['clocks/u_pll/PLLA_inst'][1]['CLKOUT1'].strip()==cells['tx_divider'][1]['HCLKIN'].strip()
ethernet_clock={'pll_output_mhz':250,'mac_clock_mhz':125,'divider':'tx_divider',
                'kind':'dedicated CLKDIV','clock_net':cells['tx_divider'][1]['CLKOUT'].strip()}
assert re.search(r'defparam\s+\\?tx_divider\s*\.DIV_MODE\s*=\s*"2"',physical.read_text(encoding='utf-8'))
generated_pll=(PROJECT/'.local/platform/ethernet_pll_mod.v').read_text()
assert 'defparam PLLA_inst.ODIV1_SEL = 3;' in generated_pll
assert len(rx_samples)==5,rx_samples
for name in rx_samples:
    kind,pins=cells[name]
    delay=[(n,p) for n,(k,p) in cells.items() if k=='IODELAY' and p.get('DO','').strip()==pins['D'].strip()]
    assert len(delay)==1,(name,delay)
    input_buf=[p for n,(k,p) in cells.items() if k=='IBUF' and p.get('O','').strip()==delay[0][1]['DI'].strip()]
    assert len(input_buf)==1 and input_buf[0]['I'].strip().startswith('rgmii_rx'),(name,input_buf)
    clock_buf=[p for n,(k,p) in cells.items() if k=='IBUF' and p.get('O','').strip()==pins['CLK'].strip()]
    assert len(clock_buf)==1 and clock_buf[0]['I'].strip()=='rgmii_rx_clk'
rx_pointer_src=select_pins('mac/rx_fifo/fifo_inst/wr_ptr_sync_commit_reg*/Q')
rx_pointer_dst=select_pins('mac/rx_fifo/fifo_inst/wr_ptr_commit_sync_reg*/D')
assert len(rx_pointer_src)==len(rx_pointer_dst)==13,(rx_pointer_src,rx_pointer_dst)
assert sorted(normalize(allpins[p][1]) for p in rx_pointer_src)==sorted(normalize(allpins[p][1]) for p in rx_pointer_dst)
for group in (rx_pointer_src,rx_pointer_dst):
    assert len({cells[p.rsplit('/',1)[0]][1]['CE'].strip() for p in group})==1
parser_pointer_src=select_pins('detection_fifo/wr_ptr_sync_commit_reg*/Q')
parser_pointer_dst=select_pins('detection_fifo/wr_ptr_commit_sync_reg*/D')
assert len(parser_pointer_src)==len(parser_pointer_dst)==10
assert sorted(normalize(allpins[p][1]) for p in parser_pointer_src)==sorted(normalize(allpins[p][1]) for p in parser_pointer_dst)
mailbox_src=select_pins('detection_mailbox/held*/Q')
mailbox_dst=select_pins('detection_mailbox/dst_data*/D')
assert len(mailbox_src)==len(mailbox_dst) and len(mailbox_src)>=308,(len(mailbox_src),len(mailbox_dst))
assert sorted(normalize(allpins[p][1]) for p in mailbox_src)==sorted(normalize(allpins[p][1]) for p in mailbox_dst)
result={'netlist_sha256':hashlib.sha256((BUILD/'impl/gwsynthesis/a745.vg').read_bytes()).hexdigest(),
        'timing_sdc_sha256':hashlib.sha256((PROJECT/'constraints/timing.sdc').read_bytes()).hexdigest(),
        'vendor_internal_model_sha256':vendor_sha,
        'internal_selector_basis':'matching vendor plaintext model; active final tool constraints required separately',
        'routed_netlist_used':physical_current,
        'routed_netlist_sha256':hashlib.sha256(physical.read_bytes()).hexdigest() if physical_current else None,
        'ddr_exception_targets':records,'tx_oddr_q_route_targets':tx_q,'ethernet_clock':ethernet_clock,
        'net_fifo_bundled_pointer':bundled_pointer,'rx_iddr_count':len(rx_samples),'rx_iddr_cells':rx_samples,
        'rx_fifo_bundled_pointer_bits':len(rx_pointer_src),'parser_fifo_bundled_pointer_bits':len(parser_pointer_src),'detection_mailbox_payload_bits':len(mailbox_src),
        'hardware_programmed':False}
report=OUT/'CONSTRAINT-TARGETS.json'
temporary=report.with_suffix('.tmp')
temporary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
temporary.replace(report)
print(json.dumps([{'groups':[len(g) for g in row['groups']], 'destination_types':dict(Counter(p['type'] for p in row['groups'][-1]))} for row in records],indent=2))
