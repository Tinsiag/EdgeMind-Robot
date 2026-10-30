"""Audit LCD launch/sample at routed pads. No claim of measured cable delay."""
import hashlib,json,re
from pathlib import Path
from audit_tx_sdf import clean,edge_values
OUT=Path(__file__).resolve().parent
BUILD=OUT.parents[1]/'code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous'
PNR=BUILD/'impl/pnr'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 b=json.loads((BUILD/'result.json').read_text())
 assert b['compile_passed'] and b['camera_size']==[800,480]
 sdf=(PNR/'a745.sdf').read_text();vo=(PNR/'a745.vo').read_text()
 assert '(TIMESCALE 1 ns)' in sdf
 cells={}
 for block in re.split(r'(?m)^  \(CELL\s*$',sdf)[1:]:
  name=clean(re.search(r'\(INSTANCE\s*([^)]*)\)',block)[1])
  cells[name]=(re.search(r'\(CELLTYPE "([^"]+)"\)',block)[1],block)
 nets={(clean(s),clean(d)):edge_values(v) for s,d,v in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+((?:\([^()]*\)\s*)+)\)',sdf)}
 logic={clean(n):(k,{p:clean(v) for p,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',body,re.S)})
  for k,n,body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);',vo,re.S)}
 def arc(cell,src,dst):
  m=re.findall(r'\(IOPATH\s+'+re.escape(src)+r'\s+'+dst+r'\s+((?:\([^()]*\)\s*)+)\)',cells[cell][1])
  assert len(m)==1,(cell,src,dst)
  return edge_values(m[0])
 endpoints={name:(k,p) for name,(k,p) in logic.items() if k=='OBUF' and p['O'].startswith('tft_') and p['O']!='tft_bl'}
 assert len(endpoints)==20,len(endpoints)
 clock='tft_clock';assert logic[clock][0] in ('ODDR','ODDRC')
 assert logic[clock][1]['D0']=='GND' and logic[clock][1]['D1']=='VCC',logic[clock]
 origin='display_clocks/u_pll/PLLA_inst/CLKOUT0'
 totals={};details={}
 for buf,(kind,pins) in endpoints.items():
  drivers=[(n,k,p) for n,(k,p) in logic.items() if (k.startswith('DFF') and p.get('Q')==pins['I']) or (k in ('ODDR','ODDRC') and p.get('Q0')==pins['I'])]
  assert len(drivers)==1,(buf,drivers)
  cell,kind,p=drivers[0];q='Q0' if kind in ('ODDR','ODDRC') else 'Q'
  assert p['CLK']==logic[clock][1]['CLK'],(cell,p)
  assert kind in ('ODDR','ODDRC','DFFCE','DFFC','DFFE','DFF'),kind
  routes={'clock_route':nets[(origin,cell+'/CLK')],'clock_to_q':arc(cell,'CLK',q),
          'output_route':nets[(cell+'/'+q,buf+'/I')],'obuf':arc(buf,'I','O')}
  totals[pins['O']]={}
  for edge in range(2):
   # Inverted ODDR: falling internal clock produces rising sample PCLK.
   launch=1-edge if kind in ('ODDR','ODDRC') else 0
   totals[pins['O']][('rise','fall')[edge]]=[sum(routes[key][launch if key=='clock_route' else edge][i] for key in routes) for i in range(3)]
  details[pins['O']]={'cell':cell,'type':kind,'routes':routes}
 half=1000/33/2;sample=totals['tft_clk']['rise'];windows={}
 for name,edges in totals.items():
  if name=='tft_clk':continue
  windows[name]={}
  for edge,values in edges.items():
   windows[name][edge]={'setup_ns':[half+sample[i]-v for i,v in enumerate(values)],
                        'hold_ns':[half+v-sample[i] for i,v in enumerate(values)]}
 setup=min(v for edges in windows.values() for row in edges.values() for v in row['setup_ns'])
 hold=min(v for edges in windows.values() for row in edges.values() for v in row['hold_ns'])
 # Use the stricter 10ns AT043TN24 input budget; HX8264-D03 uses8ns.
 # Allow1ns for unmeasured PCB/cable skew and0.3ns for PLL phase/jitter.
 margin=min(setup,hold)-10-1-.3
 pulse_high=[2*half+totals['tft_clk']['fall'][i]-totals['tft_clk']['rise'][i]-half for i in range(3)]
 pulse_low=[2*half-x for x in pulse_high]
 duty_pass=min(pulse_high+pulse_low)>=0.4*2*half and max(pulse_high+pulse_low)<=0.6*2*half
 out={'passed':margin>=0 and duty_pass,'clock_40_to_60_percent_duty_pass':duty_pass,'method':'same PLL output origin; routed clock + CLK/Q + output route + OBUF, all RGB/DE/HS/VS transitions, three SDF PVT corners; PCLK rising centered half-cycle after data launch',
      'bitstream_sha256':b['artifact_sha256'],'sdf_sha256':sha(PNR/'a745.sdf'),'physical_netlist_sha256':sha(PNR/'a745.vo'),
      'sample_edge':'rising','frequency_mhz':33,'corner_order':['fast','typical','slow'],
      'required_setup_hold_ns':10,'requirement_source':'Conservative 10ns AT043TN24-V1 input budget, stricter than the 8ns HX8264-D03 reference; actual module identity remains unconfirmed',
      'unmeasured_board_cable_skew_budget_ns':1,'clock_reserve_ns':.3,'board_signals_measured':False,
      'minimum_setup_ns':setup,'minimum_hold_ns':hold,'margin_ns':margin,
      'pclk_high_ns':pulse_high,'pclk_low_ns':pulse_low,'windows':windows,'arrival_ns':totals,'components':details}
 (OUT/'TFT-PAD-TIMING.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k not in ('windows','arrival_ns','components')},indent=2))
 assert out['passed'],'LCD pad timing budget exceeded'
if __name__=='__main__':main()
