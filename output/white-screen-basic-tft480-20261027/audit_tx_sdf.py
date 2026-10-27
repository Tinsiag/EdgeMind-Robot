"""Compare actual forwarded-clock/data pad delays from one routed SDF.

This supplements STA because Gowin's output generated-clock object does not
propagate its source latency. It is a model/corner audit, not a board measure.
"""
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
BUILD=REPO/'code/camera-car-control/a741-fpga-fusion/.local/gowin-basic-tft480-screen-test-diagnostic'
PNR=BUILD/'impl/pnr'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def clean(value): return value.replace('\\','').strip()
def triple(text):
    values=[float(x) for x in text.split(':')]
    assert len(values)==3, text
    return values

def edge_values(text):
    values=[triple(x) for x in re.findall(r'\(([^()]*)\)',text)]
    assert len(values) in (1,2),text
    return values if len(values)==2 else [values[0],values[0]]

def main():
    result=json.loads((BUILD/'result.json').read_text())
    assert result['compile_passed'] and result['run_state']!='running'
    sdf_path=PNR/'a741.sdf';vo_path=PNR/'a741.vo'
    assert min(sdf_path.stat().st_mtime,vo_path.stat().st_mtime)>=result['started_unix']
    sdf=sdf_path.read_text(encoding='utf-8');vo=vo_path.read_text(encoding='utf-8')
    assert '(TIMESCALE 1 ns)' in sdf
    cells={}
    for block in re.split(r'(?m)^  \(CELL\s*$',sdf)[1:]:
        kind=re.search(r'\(CELLTYPE "([^"]+)"\)',block)[1]
        name=clean(re.search(r'\(INSTANCE\s*([^)]*)\)',block)[1])
        cells[name]=(kind,block)
    nets={}
    for source,dest,delays in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+((?:\([^()]*\)\s*)+)\)',sdf):
        key=(clean(source),clean(dest))
        assert key not in nets,key
        nets[key]=edge_values(delays)
    logical={}
    for kind,name,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo,re.S):
        logical[clean(name)]=(kind,{p:clean(n) for p,n in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)})
    def arc(cell,src,dst,kind):
        assert cells[cell][0]==kind,(cell,cells[cell][0])
        # One triple applies to both output edges; two mean rise then fall.
        # Reject conditional/edge-specific forms rather than approximate them.
        matches=re.findall(r'\(IOPATH\s+'+re.escape(src)+r'\s+'+re.escape(dst)+r'\s+((?:\([^()]*\)\s*)+)\)',cells[cell][1])
        assert len(matches)==1,(cell,src,dst)
        return edge_values(matches[0])
    endpoints={'rgmii_tx_clk':('transmitter/U_ODDR_clk1','rgmii_tx_clk_obuf'),
               'rgmii_tx_ctl':('transmitter/U_ODDR_en1','rgmii_tx_ctl_obuf')}
    endpoints.update({f'rgmii_txd[{i}]':(f'transmitter/[{i}].U_ODDR_dq1',f'rgmii_txd_{i}_obuf') for i in range(4)})
    totals={};details={};clocknets=set()
    for port,(ddr,buf) in endpoints.items():
        assert logical[ddr][0]=='ODDR' and logical[buf][0]=='OBUF'
        assert logical[ddr][1]['Q0']==logical[buf][1]['I']
        assert logical[buf][1]['O']==port,(port,logical[buf])
        clocknets.add(logical[ddr][1]['CLK'])
        routes={
            'clock_route':nets[('tx_divider/CLKOUT',ddr+'/CLK')],
            'clock_to_q':arc(ddr,'CLK','Q0','ODDR'),
            'output_route':nets[(ddr+'/Q0',buf+'/I')],
            'output_buffer':arc(buf,'I','O','OBUF')}
        totals[port]={}
        for launch in range(2):
            for transition in range(2):
                if port=='rgmii_tx_clk' and transition!=launch:continue
                label=('rise','fall')[launch]+'CLK_'+('rise','fall')[transition]+'DATA'
                totals[port][label]=[round(routes['clock_route'][launch][i]+sum(routes[k][transition][i]
                    for k in ('clock_to_q','output_route','output_buffer')),6) for i in range(3)]
        details[port]=routes
    assert len(clocknets)==1
    clock=totals['rgmii_tx_clk'];skews={}
    for port,values in totals.items():
        if port!='rgmii_tx_clk':
            skews[port]={}
            for label,delays in values.items():
                clock_label='riseCLK_riseDATA' if label.startswith('riseCLK') else 'fallCLK_fallDATA'
                skews[port][label]=[round(value-clock[clock_label][i],6) for i,value in enumerate(delays)]
    worst=max(abs(v) for port in skews.values() for row in port.values() for v in row)
    # 35ps uncertainty reserve and 0.2ns unmeasured PCB skew budget.
    margin=round(0.5-0.2-0.035-worst,6)
    record={'passed':margin>=0,'sdf_sha256':sha(sdf_path),'physical_netlist_sha256':sha(vo_path),
            'bitstream_sha256':result['artifact_sha256'],'corner_order':['fast','typical','slow'],
            'edge_model':'one or two SDF triples; all four launch-clock / data-transition combinations, three PVT corners',
            'method':'shared tx_divider origin; sum clock route + ODDR CLK/Q0 + pad route + OBUF I/O, subtract forwarded clock in each corner',
            'arrival_delay_ns':totals,'path_components_ns':details,'data_minus_clock_ns':skews,
            'worst_abs_skew_ns':worst,'uncertainty_reserve_ns':0.035,'board_skew_budget_ns':0.2,
            'allowed_total_skew_ns':0.5,'margin_ns':margin,'board_skew_measured':False}
    (OUT/'TX-SKEW-REVIEW.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    assert record['passed'],'TX pad skew exceeds Table58 budget'

if __name__=='__main__':main()
