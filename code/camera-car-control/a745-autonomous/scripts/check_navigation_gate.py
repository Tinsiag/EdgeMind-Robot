"""Execute current-source Gowin gate models; bind them to the board synthesis inputs."""
import hashlib,json,re,subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
def main():
 main_netlist=ROOT/'.local/gowin-a745-autonomous/impl/gwsynthesis/a745.vg';digest=sha(main_netlist)
 main_text=main_netlist.read_text()
 envelope=re.search(r'(?ms)^module a745_turn_envelope\s*\(.*?^endmodule',main_text)
 assert envelope and 'SDPB ' not in envelope[0]
 # Keep a revision-specific receipt so a timed-out prior gate cannot be
 # mistaken for the current run or contaminate its generated netlists.
 out=ROOT/'.local/navigation-gate-check-74508';out.mkdir(exist_ok=True)
 primitive=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
 sources=[ROOT/'rtl/a745_navigation_scan.v',ROOT/'rtl/a745_turn_envelope.v',ROOT/'rtl/a745_autonomy.v',ROOT/'lib/a741_motion_feedback.v',ROOT/'rtl/a745_lidar_filter.v',ROOT/'lib/a741_attitude.v']
 inputs=[primitive,Path(__file__).resolve()]+sources;models=[]
 prefix=['wsl.exe','-d','Ubuntu-26.04','--cd',linux(ROOT),'--exec']
 for module,bench_name,source in [('a745_navigation_scan','navigation_scan_tb',sources[0]),('a745_autonomy','autonomy_tb',sources[2]),('a741_motion_feedback','motion_feedback_tb',sources[3]),('a745_lidar_filter','lidar_filter_tb',sources[4]),('a741_attitude','attitude_filter_tb',sources[5])]:
  folder=out/module;folder.mkdir(exist_ok=True);top_name=module+'_gate_probe'
  header=re.search(r'(?ms)^module '+module+r'.*?\);',source.read_text())[0]
  header=re.sub(r'#\(parameter.*?\)\(', '(', header,flags=re.S)
  header=header.replace('module '+module,'module '+top_name).replace('output reg','output wire')
  params='#(.GEOMETRY_VERIFIED(1))' if module=='a745_autonomy' else ''
  top=folder/'probe.v';top.write_text(header+'\n'+module+' '+params+' dut(.*);\nendmodule\n')
  project=ET.Element('Project');ET.SubElement(project,'Version').text='5'
  ET.SubElement(project,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002'
  listing=ET.SubElement(project,'FileList')
  for path in [top]+sources:ET.SubElement(listing,'File',path=path.as_posix(),type='file.verilog',enable='1')
  (folder/'probe.gprj').write_bytes(ET.tostring(project,encoding='utf-8',xml_declaration=True))
  tcl=folder/'build.tcl';tcl.write_text('cd [file dirname [file normalize [info script]]]\nopen_project probe.gprj\nset_option -top_module '+top_name+'\nset_option -output_base_name probe\nset_option -verilog_std sysv2017\nrun syn\n')
  with (folder/'synthesis.log').open('w') as log:
   subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
  netlist=folder/'impl/gwsynthesis/probe.vg'
  original=ROOT/'tests'/f'{bench_name}.v';inputs.append(original);bench=folder/'test.v'
  body=original.read_text().replace('module '+bench_name+';','module '+bench_name+";\n GSR GSR(.GSRI(1'b1));")
  body=body.replace('a745_autonomy #(.GEOMETRY_VERIFIED(1))','a745_autonomy')
  body=body.replace(module+' dut(',top_name+' dut(');bench.write_text(body)
  product=folder/'test.vvp'
  commands=[prefix+['iverilog','-g2012','-s',bench_name,'-o',linux(product),linux(bench),linux(netlist),linux(primitive)],prefix+['timeout','60s','vvp',linux(product)]]
  for phase,command in zip(['compile','execute'],commands):
   p=subprocess.run(command,capture_output=True,text=True,errors='replace',timeout=70)
   (folder/f'{phase}.log').write_text(p.stdout+p.stderr,encoding='utf-8')
   assert p.returncode==0,(module,phase,p.stdout+p.stderr)
   if phase=='execute':assert 'PASS ' in p.stdout,p.stdout+p.stderr
  models.append({'module':module,'test':bench_name,'netlist_sha256':sha(netlist)})
  print('PASS Gowin primitive model: '+bench_name,flush=True)
 # Reuse the same observable autonomous model for fault-time and reverse tests.
 folder=out/'a745_autonomy';netlist=folder/'impl/gwsynthesis/probe.vg'
 for bench_name in ['imu_fault_latch_tb','reverse_escape_tb']:
  original=ROOT/'tests'/f'{bench_name}.v';inputs.append(original)
  bench=folder/f'{bench_name}.v';body=original.read_text().replace('module '+bench_name+';', 'module '+bench_name+";\n GSR GSR(.GSRI(1'b1));")
  body=body.replace('a745_autonomy #(.GEOMETRY_VERIFIED(1)) dut(', 'a745_autonomy_gate_probe dut(');bench.write_text(body)
  product=folder/f'{bench_name}.vvp'
  for phase,command in [('compile',prefix+['iverilog','-g2012','-s',bench_name,'-o',linux(product),linux(bench),linux(netlist),linux(primitive)]),('execute',prefix+['timeout','60s','vvp',linux(product)])]:
   p=subprocess.run(command,capture_output=True,text=True,errors='replace',timeout=70)
   (folder/f'{bench_name}-{phase}.log').write_text(p.stdout+p.stderr,encoding='utf-8')
   assert p.returncode==0,p.stdout+p.stderr
   if phase=='execute':assert 'PASS ' in p.stdout,p.stdout+p.stderr
  models.append({'module':'a745_autonomy','test':bench_name,'netlist_sha256':sha(netlist)})
  print('PASS Gowin primitive model: '+bench_name,flush=True)
 # Execute the connected attitude/session path using both independently
 # synthesized leaf models. This is not an optimized full-board simulation.
 bench_name='attitude_session_tb';original=ROOT/'tests'/f'{bench_name}.v';inputs.append(original)
 folder=out/'a741_attitude';bench=folder/f'{bench_name}.v'
 body=original.read_text().replace('module '+bench_name+';', 'module '+bench_name+";\n GSR GSR(.GSRI(1'b1));")
 body=body.replace('a741_attitude attitude(', 'a741_attitude_gate_probe attitude(')
 body=body.replace('a745_autonomy #(.GEOMETRY_VERIFIED(1)) session(', 'a745_autonomy_gate_probe session(')
 bench.write_text(body);product=folder/f'{bench_name}.vvp'
 netlists=[folder/'impl/gwsynthesis/probe.vg',out/'a745_autonomy/impl/gwsynthesis/probe.vg']
 for phase,command in [('compile',prefix+['iverilog','-g2012','-s',bench_name,'-o',linux(product),linux(bench),*map(linux,netlists),linux(primitive)]),('execute',prefix+['timeout','60s','vvp',linux(product)])]:
  p=subprocess.run(command,capture_output=True,text=True,errors='replace',timeout=70)
  (folder/f'{bench_name}-{phase}.log').write_text(p.stdout+p.stderr,encoding='utf-8')
  assert p.returncode==0,p.stdout+p.stderr
  if phase=='execute':assert 'PASS ' in p.stdout,p.stdout+p.stderr
 models.append({'module':'a741_attitude+a745_autonomy','test':bench_name,'netlist_sha256':[sha(p) for p in netlists]})
 print('PASS Gowin primitive models connected: '+bench_name,flush=True)
 assert sha(main_netlist)==digest,'Board netlist changed during gate execution'
 receipt={'passed':True,'main_netlist_sha256':digest,'tests':models,'model_scope':'Independent synthesis of current leaf inputs with full observable ports; main board optimizer crosses hierarchy boundaries. Main envelope separately checked for asynchronous ROM mapping.','asynchronous_turn_rom_synchronous_ram_count':0,'actual_board_tested':False,'input_sha256':{str(p):sha(p) for p in inputs}}
 (ROOT/'.local/tests/navigation-gate-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
