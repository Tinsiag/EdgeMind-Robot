"""Build the sole A745 autonomous profile. Never invokes board operations."""
import argparse,hashlib,json,re,shutil,subprocess,threading,time
from pathlib import Path
from xml.etree import ElementTree as ET
from prepare import prepare,ROOT

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','synth','build','pnr']);ap.add_argument('--timeout',type=int,default=1800);args=ap.parse_args()
 out=ROOT/'.local/gowin-a745-autonomous';out.mkdir(parents=True,exist_ok=True)
 previous=json.loads((out/'result.json').read_text()) if (out/'result.json').is_file() else None
 if previous and previous.get('run_state')=='running':raise RuntimeError('Unfinished compiler run; inspect it before changing frozen inputs')
 files,platform=prepare()
 if args.mode=='prepare':print(platform);return
 (out/'firmware').mkdir(exist_ok=True);shutil.copy2(ROOT/'firmware/mission.hex',out/'firmware/mission.hex')
 inputs=files+[platform/'a745.cst',platform/'a745.sdc',out/'firmware/mission.hex'];hashes={str(p):sha(p) for p in inputs}
 if args.mode=='pnr':
  if not previous or previous.get('source_sha256')!=hashes or not previous.get('synthesis_passed'):raise RuntimeError('PNR requires matching completed synthesis')
  if sha(out/'impl/gwsynthesis/a745.vg')!=previous['synthesis_netlist_sha256']:raise RuntimeError('Netlist changed')
 project=ET.Element('Project');ET.SubElement(project,'Template').text='FPGA';ET.SubElement(project,'Version').text='5'
 ET.SubElement(project,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002';listing=ET.SubElement(project,'FileList')
 for p in inputs[:-1]:ET.SubElement(listing,'File',path=p.as_posix(),type={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}[p.suffix],enable='1')
 (out/'a745.gprj').write_bytes(ET.tostring(project,encoding='utf-8',xml_declaration=True))
 options={'top_module':'a745_top','output_base_name':'a745','verilog_std':'sysv2017','use_sspi_as_gpio':1,'use_cpu_as_gpio':1,'user_code':'0000A745','bit_security':0,'route_option':1,'place_option':1,'timing_driven':1,'correct_hold_violation':1,'gen_sdf':1,'gen_verilog_sim_netlist':1}
 tcl='cd [file dirname [file normalize [info script]]]\nopen_project a745.gprj\n'+''.join(f'set_option -{k} {v}\n' for k,v in options.items())+('run syn\n' if args.mode=='synth' else 'run pnr\n' if args.mode=='pnr' else 'run all\n')
 (out/'build.tcl').write_bytes(tcl.encode());record={'profile':'A745-S1-AUTONOMOUS-TX-ONLY','run_state':'running','mode':args.mode,'source_sha256':hashes,'compile_passed':False,'synthesis_passed':False,'timing_signed_off':False,'hardware_programmed':False,'route_option':1,'place_option':1,'network_control_enabled':False,'motor_pads_dynamic':True,'motor_locked':False,'screen_test':False,'motion_lidar':True,'camera_size':[800,480],'platform_directory':str(platform),'evidence_freshness_lower_bound_unix':(out/'build.tcl').stat().st_mtime}
 def save():(out/'result.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
 save();started=time.monotonic();timed_out=False
 with (out/'build.log').open('w',encoding='utf-8') as log:
  p=subprocess.Popen(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(out/'build.tcl')],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
  def reader():
   for line in p.stdout:log.write(line);log.flush()
  worker=threading.Thread(target=reader);worker.start()
  try:rc=p.wait(timeout=args.timeout)
  except subprocess.TimeoutExpired:
   subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True);rc=-1;timed_out=True
  worker.join(timeout=10)
 netlist=out/'impl/gwsynthesis/a745.vg';artifact=out/'impl/pnr/a745.fs';changed=[str(p) for p in inputs if sha(p)!=hashes[str(p)]];text=(out/'build.log').read_text(encoding='utf-8')
 record.update(returncode=rc,seconds=time.monotonic()-started,timed_out=timed_out,run_state='completed' if rc==0 else 'failed',sources_changed=changed,synthesis_passed=netlist.is_file() and 'GowinSynthesis finish' in text,compile_passed=rc==0 and not changed and not timed_out and (args.mode=='synth' or artifact.is_file()))
 if netlist.is_file():record['synthesis_netlist_sha256']=sha(netlist)
 if artifact.is_file() and args.mode!='synth':record.update(artifact=str(artifact),artifact_sha256=sha(artifact))
 report=out/'impl/pnr/a745.tr'
 if args.mode!='synth' and report.is_file() and report.stat().st_mtime>=record['evidence_freshness_lower_bound_unix']:
  tr=report.read_text(encoding='utf-8',errors='replace');frequency={}
  for name,limit,actual in re.findall(r'(?m)^\s*\d+\s+(\S+)\s+([\d.]+)\(MHz\)\s+([\d.]+)\(MHz\)',tr):frequency[name]={'constraint_mhz':float(limit),'actual_mhz':float(actual)}
  tns=tr.split('2.4 Total Negative Slack Summary\n')[-1].split('3. Timing Details')[0];violations={k:0 for k in ['setup','hold','recovery','removal']}
  for kind,count in re.findall(r'(?m)^\s*\S+\s+(setup|hold|recovery|removal)\s+-?[\d.]+\s+(\d+)\s*$',tns):violations[kind]+=int(count)
  record.update(clock_frequencies=frequency,timing_violations=violations)
 save();print(json.dumps({k:v for k,v in record.items() if k!='source_sha256'},indent=2))
 if not record['compile_passed']:raise SystemExit(1)
if __name__=='__main__':main()
