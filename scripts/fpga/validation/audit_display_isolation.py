"""Conservative primitive-netlist reachability from RX data to motor outputs."""
from collections import defaultdict,deque
import hashlib,json,re
from pathlib import Path
OUT=Path(__file__).resolve().parents[3]/'output/current-firmware'
OUT.mkdir(parents=True,exist_ok=True)
PROJECT=OUT.parents[1]/'code/camera-car-control/a745-autonomous'
BUILD=PROJECT/'.local/gowin-a745-autonomous'
PRIM=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
DECL=PRIM.with_name('prim_syn.vhd')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def signals(value):
    value=re.sub(r'\s+','',value.replace('\\',''))
    result=[]
    for part in re.split('[{},]',value):
        if not part or "'" in part:continue
        m=re.fullmatch(r'(.*)\[(\d+):(\d+)\]',part)
        if m:
            a,b=map(int,m.group(2,3));result += [f'{m[1]}[{i}]' for i in range(min(a,b),max(a,b)+1)]
        else:result.append(part)
    return result
def trace(vo,seeds=None):
    outputs={};bidirectional={}
    primitive_text=re.sub(r'(?s)/\*.*?\*/|//[^\n]*','',PRIM.read_text(encoding='utf-8'))
    for name,body in re.findall(r'(?ms)^module\s+(\w+)\b(.*?)^endmodule',primitive_text):
        ports=set()
        for decl in re.findall(r'\boutput\s+([^;]+);',body):
            decl=re.sub(r'\[[^]]*\]|\b(?:reg|wire|signed|unsigned)\b','',decl)
            ports.update(re.findall(r'\b\w+\b',decl))
        outputs[name]=ports
        bidirectional[name]=set()
        for decl in re.findall(r'\binout\s+([^;]+);',body):
            bidirectional[name].update(re.findall(r'\b\w+\b',re.sub(r'\[[^]]*\]|\b(?:reg|wire|signed|unsigned)\b','',decl)))
        outputs[name].update(bidirectional[name])
    # DQS's Verilog model is encrypted. Its public port directions are in
    # the matching vendor VHDL component library; retain all dependencies.
    declarations=DECL.read_text(encoding='utf-8')
    dqs=re.search(r'(?is)COMPONENT\s+DQS\b(.*?)end\s+COMPONENT',declarations)[1]
    outputs['DQS']=set()
    for names in re.findall(r'(?im)^\s*([\w, ]+)\s*:\s*out\b',dqs):
        outputs['DQS'].update(re.findall(r'\w+',names))
    assert outputs['DQS']=={'DQSR90','DQSW0','DQSW270','RPOINT','WPOINT','RVALID','RBURST','RFLAG','WFLAG'}
    cells=[];sinks=defaultdict(list)
    for kind,name,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo.read_text(),re.S):
        if kind=='module':continue
        assert kind in outputs,kind
        pins=dict(re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S))
        targets=[net for p,v in pins.items() if p in outputs[kind] for net in signals(v)]
        # Every data/enable/reset input conservatively influences every output.
        # Clock pins are excluded from data reachability; no RX clock is shared
        # with motion, which is independently inspected at the top-level.
        inputs=[net for p,v in pins.items() if (p not in outputs[kind] or p in bidirectional.get(kind,set())) and not re.fullmatch(r'(?:CLK\w*|[RW]CLK|FCLK|PCLK|MCLK)',p) for net in signals(v)]
        idx=len(cells);cells.append((name,targets))
        for net in inputs:sinks[net].append(idx)
    reached=set(seeds if seeds is not None else ['rgmii_rx_ctl']+[f'rgmii_rxd[{i}]' for i in range(4)])
    queue=deque(reached);visited=set()
    while queue:
        for idx in sinks[queue.popleft()]:
            if idx in visited:continue
            visited.add(idx)
            for net in cells[idx][1]:
                if net not in reached:reached.add(net);queue.append(net)
    return reached,visited

def main():
    b=json.loads((BUILD/'result.json').read_text())
    assert b['run_state']=='completed' and b['compile_passed']
    vo=BUILD/'impl/pnr/a745.vo';assert vo.stat().st_mtime>=b['evidence_freshness_lower_bound_unix']
    reached,visited=trace(vo)
    motors=['left_in1','left_in2','right_in1','right_in2']
    # FW74513 deliberately adds ET10 bounded intents. Raw RX now reaches
    # motion, so the old all-RX isolation claim would be false. Check ED10's
    # *decoded metadata* separately and bind local-session functional tests.
    assert set(motors)<=reached, sorted(set(motors)-reached)
    text=vo.read_text()
    nets=set()
    for value in re.findall(r'\.(?:Q\w*|O\w*)\((.*?)\)',text):nets.update(signals(value))
    display_sources=sorted(n for n in nets if re.fullmatch(r'detection_data\[\d+\]',n))
    assert len(display_sources)>=16,display_sources
    display_reached,display_cells=trace(vo,display_sources)
    assert not set(motors)&display_reached,sorted(set(motors)&display_reached)
    assert any(n.startswith('tft_rgb[') for n in display_reached)
    tests=json.loads((PROJECT/'.local/tests/result.json').read_text())
    assert {'mission_core_tb','task_rx_tb','motion_planner_tb'}<=set(tests['passed'])
    for name,digest in tests['input_sha256'].items():assert sha(Path(name))==digest,name
    assert 'rgmii_tx_ctl' in reached and any(net.startswith('tft_rgb[') for net in reached)
    record=dict(passed=True,bitstream_sha256=b['artifact_sha256'],physical_netlist_sha256=sha(vo),
                primitive_model_sha256=sha(PRIM),primitive_declarations_sha256=sha(DECL),data_sources=sorted(['rgmii_rx_ctl']+[f'rgmii_rxd[{i}]' for i in range(4)]),
                unreachable_motor_outputs_from_ed10_box_data=motors,
                decoded_ed10_sources=display_sources,ed10_reached_cells=len(display_cells),
                raw_rx_reaches_motor_outputs=True,local_session_regressions=['mission_core_tb','task_rx_tb','motion_planner_tb'],
                reached_cells=len(visited),reached_nets=len(reached),
                method='Conservative data/enable/reset transitive closure through all routed primitives; sequential boundaries retained as dependencies; clocks excluded',
                note='Decoded ED10 box/class/score data is isolated from motor outputs. ED10 update/ready shares transport with ET10; the diagnostic counter reaches TX RAM, whose conservative all-bit graph also reaches freshness. These control/diagnostic paths are not claimed structurally isolated. Separate checksum-correct ED10-port/magic rejection and connected local-session regressions verify display packets cannot be accepted as ET10 motion intents. No claim of all-RX isolation.')
    (OUT/'DISPLAY-ISOLATION.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
