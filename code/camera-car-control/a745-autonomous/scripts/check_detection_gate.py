"""Run new display leaves using Gowin synthesis primitives; bind board netlist."""
import hashlib,json,re,subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
def main():
 board=ROOT/'.local/gowin-a745-autonomous/impl/gwsynthesis/a745.vg';digest=sha(board)
 primitive=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
 sources=[Path(__file__).resolve(),primitive];records=[]
 for module,bench_name,param in [('a745_detection_rx','detection_rx_tb','SESSION_CYCLES(2000)'),
                                 ('a745_detection_overlay','detection_overlay_tb','TTL_FRAMES(2)')]:
  source=ROOT/'rtl'/(module+'.v');bench_source=ROOT/'tests'/(bench_name+'.v');sources += [source,bench_source]
  out=ROOT/('.local/detection-gate-74512-'+digest[:12]+'-explicit-exit')/module;out.mkdir(parents=True,exist_ok=True)
  header=re.search(r'(?ms)^module '+module+r'.*?\);',source.read_text())[0]
  header=re.sub(r'#\(parameter.*?\)\(', '(', header,flags=re.S).replace('module '+module,'module '+module+'_gate_probe').replace('output reg','output wire')
  probe=out/'probe.v';probe.write_text(header+'\n'+module+' #(.'+param+') dut(.*);\nendmodule\n')
  project=ET.Element('Project');ET.SubElement(project,'Version').text='5'
  ET.SubElement(project,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002'
  listing=ET.SubElement(project,'FileList')
  for path in [source,probe]:ET.SubElement(listing,'File',path=path.as_posix(),type='file.verilog',enable='1')
  (out/'probe.gprj').write_bytes(ET.tostring(project,encoding='utf-8',xml_declaration=True))
  tcl=out/'build.tcl';tcl.write_text('cd [file dirname [file normalize [info script]]]\nopen_project probe.gprj\nset_option -top_module '+module+'_gate_probe\nset_option -output_base_name probe\nset_option -verilog_std sysv2017\nrun syn\nexit\n')
  with (out/'synthesis.log').open('w') as log:
   subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
  bench=out/'test.v';body=bench_source.read_text().replace('module '+bench_name+';', 'module '+bench_name+";\n GSR GSR(.GSRI(1'b1));")
  body=body.replace(module+' #(.'+param+') dut',module+'_gate_probe dut').replace('dut.state',"3'd0")
  bench.write_text(body);product=out/'test.vvp';netlist=out/'impl/gwsynthesis/probe.vg'
  prefix=['wsl.exe','-d','Ubuntu-26.04','--cd',linux(ROOT),'--exec']
  for phase,cmd in [('compile',prefix+['iverilog','-g2012','-s',bench_name,'-o',linux(product),linux(bench),linux(netlist),linux(primitive)]),
                    ('execute',prefix+['vvp',linux(product)])]:
   p=subprocess.run(cmd,capture_output=True,text=True,errors='replace',timeout=90)
   (out/(phase+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
   assert p.returncode==0,p.stdout+p.stderr
   if phase=='execute':assert 'PASS' in p.stdout,p.stdout+p.stderr
  records.append(dict(module=module,bench=bench_name,netlist_sha256=sha(netlist)))
  print('PASS Gowin display primitive model: '+bench_name,flush=True)
 assert sha(board)==digest
 (ROOT/'.local/tests/detection-gate-result.json').write_text(json.dumps(dict(passed=True,main_netlist_sha256=digest,
   scope='Independently synthesized display leaves, not optimized full-board execution',tests=records,
   input_sha256={str(p):sha(p) for p in sources}),indent=2)+'\n')
if __name__=='__main__':main()
