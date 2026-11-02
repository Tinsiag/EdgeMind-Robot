"""Build the sole A745 autonomous profile. Never invokes board operations."""
import argparse,hashlib,html,json,os,re,shutil,subprocess,threading,time
from pathlib import Path
from xml.etree import ElementTree as ET
from prepare import prepare,ROOT

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def path_violations(text,html_report=False):
 paths={}
 headings=['Setup Paths Table','Hold Paths Table','Recovery Paths Table','Removal Paths Table','Minimum Pulse Width Table']
 for index,kind in enumerate(['setup','hold','recovery','removal']):
  start=text.rfind(headings[index])
  if start<0:continue
  ends=[text.find(name,start+len(headings[index])) for name in headings[index+1:]]
  end=min([i for i in ends if i>=0] or [len(text)])
  segment=text[start:end]
  pattern=r'(?m)^\s*\d+\s+(-?[\d.]+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+'
  rows=re.findall(pattern,segment)
  if not rows and 'Nothing to report!' not in segment:raise RuntimeError(f'No {kind} path rows parsed; timing report format requires review')
  bad=[{'slack_ns':float(s),'from':f,'to':t,'from_clock':fc,'to_clock':tc} for s,f,t,fc,tc in rows if float(s)<0]
  if bad:paths[kind]=bad
 start=text.rfind('Minimum Pulse Width Table')
 end=text.find('Timing Report By Analysis Type',start)
 pulse=re.findall(r'(?m)^\s*\d+\s+(-?[\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(High|Low) Pulse Width\s+(\S+)\s+(\S+)',text[start:end])
 if not pulse and 'Nothing to report!' not in text[start:end]:raise RuntimeError('No minimum pulse rows parsed')
 pulse_bad=[{'slack_ns':float(s),'actual_ns':float(a),'required_ns':float(r),'type':e,'clock':c,'object':o} for s,a,r,e,c,o in pulse if float(s)<0]
 if pulse_bad:paths['minimum_pulse_width']=pulse_bad
 if not any(heading in text for heading in headings):raise RuntimeError('No timing path tables found')
 return paths
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','synth','build','pnr']);ap.add_argument('--timeout',type=int,default=1800);args=ap.parse_args()
 out=ROOT/'.local/gowin-a745-autonomous';out.mkdir(parents=True,exist_ok=True)
 previous=json.loads((out/'result.json').read_text()) if (out/'result.json').is_file() else None
 if previous and previous.get('run_state')=='running':raise RuntimeError('Unfinished compiler run; inspect it before changing frozen inputs')
 files,platform=prepare()
 if args.mode=='prepare':print(platform);return
 (out/'firmware').mkdir(exist_ok=True);shutil.copy2(ROOT/'firmware/mission.hex',out/'firmware/mission.hex')
 inputs=files+[platform/'a745.cst',platform/'a745.sdc',out/'firmware/mission.hex'];hashes={str(p):sha(p) for p in inputs}
 constraint_changes=[]
 if args.mode=='pnr':
  if not previous or not previous.get('synthesis_passed'):raise RuntimeError('PNR requires completed synthesis')
  before=previous.get('source_sha256',{})
  constraint_changes=[name for name in hashes if before.get(name)!=hashes[name]]
  # A timing-only reroute may reuse the exact netlist. RTL, firmware, pin
  # assignments and the complete input set must still match the synthesis.
  if set(before)!=set(hashes) or any(name!=str(platform/'a745.sdc') for name in constraint_changes):raise RuntimeError('PNR reuse permits only timing SDC changes; RTL/CST/firmware require synthesis')
  if sha(out/'impl/gwsynthesis/a745.vg')!=previous['synthesis_netlist_sha256']:raise RuntimeError('Netlist changed')
 project=ET.Element('Project');ET.SubElement(project,'Template').text='FPGA';ET.SubElement(project,'Version').text='5'
 ET.SubElement(project,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002';listing=ET.SubElement(project,'FileList')
 for p in inputs[:-1]:ET.SubElement(listing,'File',path=p.as_posix(),type={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}[p.suffix],enable='1')
 (out/'a745.gprj').write_bytes(ET.tostring(project,encoding='utf-8',xml_declaration=True))
 options={'top_module':'a745_top','output_base_name':'a745','verilog_std':'sysv2017','use_sspi_as_gpio':1,'use_cpu_as_gpio':1,'user_code':'0000A745','bit_security':0,'route_option':int(os.environ.get('GOWIN_ROUTE_OPTION','1')),'place_option':int(os.environ.get('GOWIN_PLACE_OPTION','1')),'timing_driven':1,'correct_hold_violation':1,'gen_sdf':1,'gen_verilog_sim_netlist':1}
 if 'GOWIN_CLOCK_ROUTE_ORDER' in os.environ:
  order=int(os.environ['GOWIN_CLOCK_ROUTE_ORDER'])
  if order not in (0,1):raise ValueError('Clock route order must be 0 or 1')
  options['clock_route_order']=order
 tcl='cd [file dirname [file normalize [info script]]]\nopen_project a745.gprj\n'+''.join(f'set_option -{k} {v}\n' for k,v in options.items())+('run syn\n' if args.mode=='synth' else 'run pnr\n' if args.mode=='pnr' else 'run all\n')
 (out/'build.tcl').write_bytes(tcl.encode());record={'profile':'A745-S1-AUTONOMOUS-DISPLAY-RX','run_state':'running','mode':args.mode,'source_sha256':hashes,'compile_passed':False,'synthesis_passed':False,'timing_signed_off':False,'hardware_programmed':False,'route_option':options['route_option'],'place_option':options['place_option'],'network_control_enabled':False,'motor_pads_dynamic':True,'motor_locked':False,'screen_test':False,'motion_lidar':True,'camera_size':[800,480],'platform_directory':str(platform),'evidence_freshness_lower_bound_unix':(out/'build.tcl').stat().st_mtime}
 if 'clock_route_order' in options:record['clock_route_order']=options['clock_route_order']
 if args.mode=='pnr':record.update(synthesis_netlist_reused=True,reused_synthesis_netlist_sha256=previous['synthesis_netlist_sha256'],timing_only_changed_inputs=constraint_changes)
 def save():(out/'result.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
 save();started=time.monotonic();timed_out=False
 with (out/'build.log').open('w',encoding='utf-8') as log:
  gowin=Path(os.environ.get('GOWIN_HOME',r'C:\Gowin\Gowin_V1.9.12.04_x64'))
  gw_sh=gowin/'IDE/bin/gw_sh.exe'
  if not gw_sh.is_file(): raise FileNotFoundError(f'Gowin Shell not found: {gw_sh}')
  p=subprocess.Popen([str(gw_sh),str(out/'build.tcl')],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
  def reader():
   for line in p.stdout:log.write(line);log.flush()
  worker=threading.Thread(target=reader);worker.start()
  try:rc=p.wait(timeout=args.timeout)
  except subprocess.TimeoutExpired:
   subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True);rc=-1;timed_out=True
  worker.join(timeout=10)
 netlist=out/'impl/gwsynthesis/a745.vg';artifact=out/'impl/pnr/a745.fs';changed=[str(p) for p in inputs if sha(p)!=hashes[str(p)]];text=(out/'build.log').read_text(encoding='utf-8')
 record.update(returncode=rc,seconds=time.monotonic()-started,timed_out=timed_out,run_state='completed' if rc==0 else 'failed',sources_changed=changed,synthesis_passed=netlist.is_file() and ('GowinSynthesis finish' in text or args.mode=='pnr'),compile_passed=rc==0 and not changed and not timed_out and (args.mode=='synth' or artifact.is_file()))
 if netlist.is_file():record['synthesis_netlist_sha256']=sha(netlist)
 if args.mode=='pnr' and record.get('synthesis_netlist_sha256')!=previous['synthesis_netlist_sha256']:
  record.update(synthesis_passed=False,compile_passed=False,reused_synthesis_changed=True)
 if artifact.is_file() and args.mode!='synth':record.update(artifact=str(artifact),artifact_sha256=sha(artifact))
 # Gowin 1.9.12 writes the timing report as HTML (a745_tr_content.html) and
 # leaves a745.tr absent; accept either and flatten the tables to text.
 from timing_report import current_report
 report,tr=current_report(out/'impl/pnr',record['evidence_freshness_lower_bound_unix'])
 if args.mode!='synth' and report is not None:
  frequency={}
  for name,limit,actual in re.findall(r'(?m)^\s*\d+\s+(\S+)\s+([\d.]+)\(MHz\)\s+([\d.]+)\(MHz\)',tr):frequency[name]={'constraint_mhz':float(limit),'actual_mhz':float(actual)}
  tns=re.split(r'Total Negative Slack Summary',tr)[-1];tns=re.split(r'Timing Details',tns)[0]
  violations={k:0 for k in ['setup','hold','recovery','removal']};endpoints={}
  for name,kind,slack,count in re.findall(r'(?mi)^\s*(\S+)\s+(setup|hold|recovery|removal)\s+(-?[\d.]+)\s+(\d+)\s*$',tns):
   violations[kind.lower()]+=int(count)
   if int(count):endpoints.setdefault(name,{})[kind.lower()]={'tns_ns':float(slack),'endpoints':int(count)}
  record.update(clock_frequencies=frequency,timing_violations=violations,timing_violation_clocks=endpoints,
   timing_report=str(report))
  # The per-clock TNS summary counts only clock-to-clock checks. set_max_delay
  # endpoints report "N/A" as the capture clock and are invisible there, so
  # scan the path tables too and record every negative slack separately.
  paths=path_violations(tr,report.suffix=='.html')
  record['path_slack_violations']=paths
  record['max_delay_violations']=[p for p in paths.get('setup',[]) if p['to_clock']=='N/A']
  record['timing_signed_off']=sum(violations.values())==0 and not paths
 save();print(json.dumps({k:v for k,v in record.items() if k!='source_sha256'},indent=2))
 if not record['compile_passed'] or (args.mode!='synth' and not record['timing_signed_off']):raise SystemExit(1)
if __name__=='__main__':main()
