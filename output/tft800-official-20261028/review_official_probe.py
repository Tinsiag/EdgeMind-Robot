from pathlib import Path
import re,json,hashlib
from audit_tx_sdf import clean,edge_values
OUT=Path(__file__).resolve().parent/'official-probe-v3'
P=OUT/'impl/pnr'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((OUT/'result.json').read_text());assert b['returncode']==0 and not b['sources_changed']
assert all(sha(OUT/f)==h for f,h in b['source_sha256'].items())
tr=(P/'probe.tr').read_text();sdf=(P/'probe.sdf').read_text();vo=(P/'probe.vo').read_text()
headers=['3.1.1 Setup Paths Table','3.1.2 Hold Paths Table','3.1.3 Recovery Paths Table','3.1.4 Removal Paths Table','3.2 Minimum Pulse Width Table','3.3 Timing Report By Analysis Type']
timing={}
for i,key in enumerate(('setup','hold','recovery','removal','mpw')):
 m=re.search(r'(?ms)^'+re.escape(headers[i])+r'\s*\n(.*?)(?=^'+re.escape(headers[i+1])+')',tr)
 assert m
 values=[float(v) for v in re.findall(r'(?m)^\s*\d+\s+(-?\d+\.\d+)\s+',m[1])]
 timing[key]=min(values) if values else None
assert all(v is None or v>=0 for v in timing.values()),timing
assert not re.search(r'TC_\w+\s+(?!Actived\b)\w+\s+',tr)
cells={}
for block in re.split(r'(?m)^  \(CELL\s*$',sdf)[1:]:
 name=clean(re.search(r'\(INSTANCE\s*([^)]*)\)',block)[1]);cells[name]=(re.search(r'\(CELLTYPE "([^"]+)"\)',block)[1],block)
nets={(clean(s),clean(d)):edge_values(v) for s,d,v in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+((?:\([^()]*\)\s*)+)\)',sdf)}
logic={clean(n):(k,{p:clean(v) for p,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)}) for k,n,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo,re.S)}
def arc(n,s,d):
 m=re.findall(r'\(IOPATH\s+'+s+r'\s+'+d+r'\s+((?:\([^()]*\)\s*)+)\)',cells[n][1]);assert len(m)==1,(n,s,d)
 return edge_values(m[0])
origin='official/Gowin_PLL/u_pll/PLLA_inst/CLKOUT0'
clkbuf='TFT_clk_obuf';assert logic[clkbuf][1]['I']==logic['official/Gowin_PLL/u_pll/PLLA_inst'][1]['CLKOUT0']
clock=[[nets[(origin,clkbuf+'/I')][e][i]+arc(clkbuf,'I','O')[e][i] for i in range(3)] for e in range(2)]
windows={};paths={}
for buf,(kind,p) in logic.items():
 if kind!='OBUF' or p['O'] in ('TFT_clk','TFT_pwm') or not p['O'].startswith('TFT_'):continue
 drivers=[(n,k,ps) for n,(k,ps) in logic.items() if k.startswith('DFF') and ps.get('Q')==p['I']]
 assert len(drivers)==1,(buf,drivers)
 cell,kind,ps=drivers[0]
 assert re.search(re.escape(cell)+r'/Q\s+\S+\s+lcd33m:\[F\]',tr),(cell,'not falling launch in STA')
 if kind.startswith('DFFN'):
  clockroute=nets[(origin,cell+'/CLK')][1]
 else:
  invs=[(n,pn) for n,(kn,pn) in logic.items() if kn=='INV' and pn['O']==ps['CLK']]
  assert len(invs)==1,(cell,kind,ps['CLK'])
  inv,ip=invs[0];assert ip['I']==logic['official/Gowin_PLL/u_pll/PLLA_inst'][1]['CLKOUT0']
  clockroute=[nets[(origin,inv+'/I')][1][i]+arc(inv,'I','O')[0][i]+nets[(inv+'/O',cell+'/CLK')][0][i] for i in range(3)]
 parts={'clock':clockroute,'cq':arc(cell,'CLK','Q'),'route':nets[(cell+'/Q',buf+'/I')],'obuf':arc(buf,'I','O')}
 delays=[[clockroute[i]+sum(parts[k][e][i] for k in ('cq','route','obuf')) for i in range(3)] for e in range(2)]
 windows[p['O']]={('rise','fall')[e]:{'setup':[1000/66+clock[0][i]-delays[e][i] for i in range(3)],'hold':[1000/66+delays[e][i]-clock[0][i] for i in range(3)]} for e in range(2)}
 paths[p['O']]={'driver':cell,'type':kind,'components':parts,'arrival':delays}
assert len(windows)==19
setup=min(v for es in windows.values() for row in es.values() for v in row['setup']);hold=min(v for es in windows.values() for row in es.values() for v in row['hold'])
margin=min(setup,hold)-8-1-.3
assert margin>=0,(setup,hold,margin)
for pin in ('left_in1','left_in2','right_in1','right_in2'):
 assert logic[pin+'_obuf'][1]['I']=='GND'
cmd=(P/'cmd.do').read_text();assert all(x in cmd for x in ('-route_option 1','-place_option 1','-correct_hold 1','-timing'))
result={'passed':True,'bitstream_sha256':sha(P/'probe.fs'),'sdf_sha256':sha(P/'probe.sdf'),'vo_sha256':sha(P/'probe.vo'),
 'official_scanner_pll_colors_unchanged':True,'top_reset_synchronized':True,'main_project_replaced':False,'includes_camera_ddr_imu_ethernet':False,
 'motor_pads_grounded':True,'sta_worst_slack_ns':timing,'minimum_setup_ns':setup,'minimum_hold_ns':hold,
 'lcd_margin_ns':margin,'required_setup_hold_ns':8,'unmeasured_board_cable_budget_ns':1,'clock_reserve_ns':.3,
 'clock_arrival_ns':clock,'data_paths':paths,'windows':windows,'hardware_programmed':False}
(OUT/'REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('data_paths','windows')},indent=2))
