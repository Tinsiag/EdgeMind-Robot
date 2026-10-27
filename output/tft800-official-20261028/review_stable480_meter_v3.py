from pathlib import Path
import re,json,hashlib
from audit_tx_sdf import clean,edge_values
OUT=Path(__file__).resolve().parent / 'stable480-meter-probe-v3'
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
clkbuf='clock_pad'
inverters=[(n,p) for n,(k,p) in logic.items() if (k=='INV' and p['O']==logic[clkbuf][1]['I']) or (k=='LUT1' and p['F']==logic[clkbuf][1]['I'])]
assert len(inverters)==1,inverters
clock_inv,inv_ports=inverters[0]
ci,co=('I0','F') if logic[clock_inv][0]=='LUT1' else ('I','O')
if logic[clock_inv][0]=='LUT1':
 assert re.search(r'defparam\s+'+re.escape(clock_inv)+r"\.INIT=2'h1;",vo),'LUT must implement NOT'
assert inv_ports[ci]==logic['official/Gowin_PLL/u_pll/PLLA_inst'][1]['CLKOUT0']
clock=[[nets[(origin,clock_inv+'/'+ci)][1-e][i]+arc(clock_inv,ci,co)[e][i]+nets[(clock_inv+'/'+co,clkbuf+'/I')][e][i]+arc(clkbuf,'I','IO')[e][i] for i in range(3)] for e in range(2)]
pad_inputs={}
for name,(kind,ports) in logic.items():
 if kind!='IOBUF':continue
 assert ports['OEN']=='GND'
 ff='clock_sync_0_s0' if name=='clock_pad' else 'read_s1_'+str(19 if name=='bl_pad' else 18 if name=='de_pad' else 17 if name=='hs_pad' else 16 if name=='vs_pad' else int(re.search(r'\[(\d+)\]',name)[1]))+'_s0'
 assert logic[ff][1]['D']==ports['O'],(name,ff,ports,logic[ff])
 pad_inputs[name]={'input_net':ports['O'],'first_sampler':ff}
 ports['O']=ports['IO']
assert len(pad_inputs)==21
assert logic['bl_pad'][1]['I']=='VCC'
windows={};paths={};omitted_split_clock_bounds={}
for buf,(kind,p) in logic.items():
 if kind not in ('OBUF','IOBUF') or p['O'] in ('TFT_clk','TFT_pwm') or not p['O'].startswith('TFT_'):continue
 drivers=[(n,k,ps) for n,(k,ps) in logic.items() if k.startswith('DFF') and ps.get('Q')==p['I']]
 assert len(drivers)==1,(buf,drivers)
 cell,kind,ps=drivers[0]
 assert re.search(re.escape(cell)+r'/Q\s+\S+\s+lcd9m:\[F\]',tr),(cell,'not falling launch in STA')
 if kind.startswith('DFFN'):
  clockroute=nets[(origin,cell+'/CLK')][1]
 else:
  invs=[(n,pn) for n,(kn,pn) in logic.items() if kn=='INV' and pn['O']==ps['CLK']]
  assert len(invs)==1,(cell,kind,ps['CLK'])
  inv,ip=invs[0];assert ip['I']==logic['official/Gowin_PLL/u_pll/PLLA_inst'][1]['CLKOUT0']
  if (origin,inv+'/I') in nets and (inv+'/O',cell+'/CLK') in nets:
   clockroute=[nets[(origin,inv+'/I')][1][i]+arc(inv,'I','O')[0][i]+nets[(inv+'/O',cell+'/CLK')][0][i] for i in range(3)]
  else:
   # Gowin omits split-inverter clock INTERCONNECT records from this SDF.
   # Bound each affected path with its same-run STA clock net delay. No
   # previous build values and no assumed zero missing routing delays.
   delays=re.findall(r'(?m)^\s*[-\d.]+\s+([\d.]+)\s+tNET\s+FF\s+\d+\s+\S+\s+'+re.escape(cell)+r'/CLK\s*$',tr)
   assert delays,(cell,'missing both SDF and STA clock path')
   latest=max(map(float,delays))+0.002 # Cover rounding of the reported STA delay.
   assert all(v==0 for edge in arc(inv,'I','O') for v in edge)
   clockroute=[0,latest,latest]
   omitted_split_clock_bounds[cell]={'min_ns':0,'max_ns':latest,'basis':'same implementation STA tNET FF at this exact endpoint; nonnegative lower bound'}
 parts={'clock':clockroute,'cq':arc(cell,'CLK','Q'),'route':nets[(cell+'/Q',buf+'/I')],'obuf':arc(buf,'I','IO' if logic[buf][0]=='IOBUF' else 'O')}
 delays=[[clockroute[i]+sum(parts[k][e][i] for k in ('cq','route','obuf')) for i in range(3)] for e in range(2)]
 windows[p['O']]={('rise','fall')[e]:{'setup':[1000/18+clock[1][i]-delays[e][i] for i in range(3)],'hold':[1000/18+delays[e][i]-clock[1][i] for i in range(3)]} for e in range(2)}
 paths[p['O']]={'driver':cell,'type':kind,'components':parts,'arrival':delays}
assert len(windows)==19
setup=min(1000/18+min(clock[1])-max(v for edge in path['arrival'] for v in edge) for path in paths.values())
hold=min(1000/18+min(v for edge in path['arrival'] for v in edge)-max(clock[1]) for path in paths.values())
margin=min(setup,hold)-10-1-.3
assert margin>=0,(setup,hold,margin)
for pin in ('left_in1','left_in2','right_in1','right_in2'):
 assert logic[pin+'_obuf'][1]['I']=='GND'
cmd=(P/'cmd.do').read_text();assert all(x in cmd for x in ('-route_option 1','-place_option 1','-correct_hold 1','-timing'))
result={'passed':True,'bitstream_sha256':sha(P/'probe.fs'),'sdf_sha256':sha(P/'probe.sdf'),'vo_sha256':sha(P/'probe.vo'),
 'omitted_split_clock_bounds':omitted_split_clock_bounds,'bound_method':'conservative cross-corner min/max; missing split-inverter clock routes bounded from same-run STA; no earlier implementation reused',
 'official_scanner_unchanged':True,'official_HW_TFT43_branch_selected':True,'pll_output_mhz':9,'active_size':[480,272],'color_geometry_adapted':True,'external_sample_edge_hypothesis':'falling','resolution_hypothesis_trial':True,'independent_pad_meters':True,'rising_edge_timing_not_qualified_for_this_trial':True,'top_reset_synchronized':True,'main_project_replaced':False,'includes_camera_ddr_imu_ethernet':False,
 'motor_pads_grounded':True,'prior_meter_attempt_failed_output_maxdelay_and_not_programmed':True,'pad_input_buffers_verified':pad_inputs,'mapping':'fixed official AB22=DE and AB21=high','meter_window_reference_cycles':50000000,'sta_worst_slack_ns':timing,'minimum_setup_ns':setup,'minimum_hold_ns':hold,
 'lcd_margin_ns':margin,'required_setup_hold_ns':10,'receiver_budget_basis':'AT043TN24 PDF pages11/12; panel model still a hypothesis','unmeasured_board_cable_budget_ns':1,'clock_reserve_ns':.3,
 'clock_arrival_ns':clock,'data_paths':paths,'windows':windows,'hardware_programmed':False}
(OUT/'REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('data_paths','windows')},indent=2))
