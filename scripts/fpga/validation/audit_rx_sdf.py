"""RGMII RX pad-to-IDDR audit, both edges and all routed SDF corners."""
import hashlib
import json
from pathlib import Path
import re
from audit_tx_sdf import clean, edge_values, triple

OUT=Path(__file__).resolve().parents[3]/'output/current-firmware'
OUT.mkdir(parents=True,exist_ok=True)
BUILD=OUT.parents[1]/'code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous'
PNR=BUILD/'impl/pnr'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    result=json.loads((BUILD/'result.json').read_text())
    assert result['compile_passed'] and result['run_state']=='completed'
    assert all(v==0 for v in result['timing_violations'].values()) and not result['path_slack_violations']
    assert min((PNR/('a745.'+s)).stat().st_mtime for s in ('sdf','vo'))>=result['evidence_freshness_lower_bound_unix']
    sdf=(PNR/'a745.sdf').read_text();vo=(PNR/'a745.vo').read_text()
    logic={clean(n):(k,{p:clean(v) for p,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)})
           for k,n,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo,re.S)}
    cells={clean(re.search(r'\(INSTANCE\s*([^)]*)\)',b)[1]):b for b in re.split(r'(?m)^  \(CELL\s*$',sdf)[1:]}
    nets={(clean(s),clean(d)):edge_values(v) for s,d,v in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+((?:\([^()]*\)\s*)+)\)',sdf)}
    def arc(cell,src,dst):
        m=re.findall(r'\(IOPATH\s+'+re.escape(src)+r'\s+'+re.escape(dst)+r'\s+((?:\([^()]*\)\s*)+)\)',cells[cell])
        assert len(m)==1,(cell,src,dst)
        return edge_values(m[0])
    def ibuf(port):
        matches=[n for n,(k,p) in logic.items() if k=='IBUF' and p.get('I')==port]
        assert len(matches)==1,(port,matches)
        return matches[0]
    clock=ibuf('rgmii_rx_clk')
    records=[]
    for port in ['rgmii_rx_ctl']+[f'rgmii_rxd[{i}]' for i in range(4)]:
        buf=ibuf(port)
        delays=[n for n,(k,p) in logic.items() if k=='IODELAY' and p['DI']==logic[buf][1]['O']]
        assert len(delays)==1,(port,delays)
        delay=delays[0]
        taps=re.findall(r'defparam\s+\\?'+re.escape(delay)+r'\s*\.C_STATIC_DLY\s*=\s*(\d+)',vo)
        assert taps==['96'],(delay,taps)
        samples=[n for n,(k,p) in logic.items() if k=='IDDR' and p['D']==logic[delay][1]['DO']]
        assert len(samples)==1,(port,samples)
        cell=samples[0]
        assert logic[cell][1]['CLK']==logic[clock][1]['O']
        data_path=[[arc(buf,'I','O')[e][c]+nets[(buf+'/O',delay+'/DI')][e][c]+arc(delay,'DI','DO')[e][c]+nets[(delay+'/DO',cell+'/D')][e][c] for c in range(3)] for e in range(2)]
        clock_path=[[arc(clock,'I','O')[e][c]+nets[(clock+'/O',cell+'/CLK')][e][c] for c in range(3)] for e in range(2)]
        checks=re.findall(r'\(SETUPHOLD\s+\((posedge|negedge) D\)\s+\((posedge|negedge) CLK\)\s+\(([^()]*)\)\s+\(([^()]*)\)\)',cells[cell])
        assert len(checks)==4,(cell,checks)
        windows=[]
        for data_edge,clk_edge,setup,hold in checks:
            de=int(data_edge=='negedge');ce=int(clk_edge=='negedge')
            setups=triple(setup);holds=triple(hold)
            # PHY guaranteed +/-1.2ns output stable window, 0.2ns PCB skew,
            # plus a separate 35ps uncertainty reserve. Check same PVT corners.
            setup_margin=[round(1.0+clock_path[ce][c]-data_path[de][c]-setups[c]-.035,6) for c in range(3)]
            hold_margin=[round(1.0+data_path[de][c]-clock_path[ce][c]-holds[c]-.035,6) for c in range(3)]
            windows.append(dict(data_edge=data_edge,clock_edge=clk_edge,setup_margin_ns=setup_margin,hold_margin_ns=hold_margin))
        records.append(dict(port=port,iddr=cell,ibuf=buf,delay_cell=delay,taps=96,data_path_ns=data_path,clock_path_ns=clock_path,checks=windows))
    minimum=min(v for r in records for w in r['checks'] for name in ('setup_margin_ns','hold_margin_ns') for v in w[name])
    sdc=(Path(result['platform_directory'])/'a745.sdc').read_text()
    for command in ['-clock rx125m -max 3.000','-clock rx125m -min 1.000',
                    '-clock rx125m -clock_fall -add_delay -max 3.000','-clock rx125m -clock_fall -add_delay -min 1.000']:
        assert command in sdc,command
    record=dict(passed=minimum>=0,bitstream_sha256=result['artifact_sha256'],sdf_sha256=sha(PNR/'a745.sdf'),
                physical_netlist_sha256=sha(PNR/'a745.vo'),rx_clock_mhz=125,
                phy_basis='RTL8211F rev1.1 Table58 integrated-delay output setup/hold >=1.2ns',
                pcb_skew_budget_ns=.2,uncertainty_reserve_ns=.035,minimum_margin_ns=minimum,
                board_signals_measured=False,inputs=records)
    (OUT/'RX-INPUT-REVIEW.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    assert record['passed'],'RX pad timing budget failed'
if __name__=='__main__':main()
