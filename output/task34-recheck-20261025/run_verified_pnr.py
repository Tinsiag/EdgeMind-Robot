"""Run route option 1 on a verified completed synthesis without rewriting RTL."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys,time

REPO=Path(__file__).resolve().parents[2]
ROOT=REPO/'code/camera-car-control/a741-fpga-fusion'
OUT=ROOT/'.local/gowin-fusion-tft480'
EVIDENCE=Path(__file__).resolve().parent/'main-route1'
sys.path.insert(0,str(ROOT/'scripts'))
from build import synthesis_timing,pulse_width_slack

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(record):
    temporary=OUT/'result.pending.json'
    temporary.write_text(json.dumps(record,indent=2),encoding='utf-8')
    temporary.replace(OUT/'result.json')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--timeout',type=int,default=3600);args=parser.parse_args()
    if args.timeout<=0:raise RuntimeError('Positive timeout required')
    previous=json.loads((OUT/'result.json').read_text())
    if previous.get('mode')!='synth' or not previous.get('compile_passed') or previous.get('sources_changed'):
        raise RuntimeError('A fresh successful synthesis is required')
    inputs=previous['source_sha256']
    if any(not Path(p).is_file() or sha(p)!=h for p,h in inputs.items()):
        raise RuntimeError('Synthesis inputs do not match')
    netlist=OUT/'impl/gwsynthesis/a741.vg'
    expected=previous['synthesis_netlist_sha256']
    if sha(netlist)!=expected:raise RuntimeError('Synthesis netlist hash mismatch')
    script=(OUT/'build.tcl').read_text()
    if script.count('run syn')!=1 or 'set_option -route_option 1\n' not in script or 'set_option -place_option 1\n' not in script:
        raise RuntimeError('Expected synthesis project with route 1/place 1')
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    for name in ('result.json','build.log','build.tcl','a741.gprj'):
        shutil.copy2(OUT/name,EVIDENCE/('synth-'+name))
    tcl=OUT/'verified-pnr.tcl';tcl.write_text(script.replace('run syn','run pnr'),encoding='utf-8')
    record={k:v for k,v in previous.items() if k not in ('artifact','artifact_sha256')}
    started=time.time();record.update(mode='pnr',run_state='running',compile_passed=False,pid=os.getpid(),
        started_unix=started,seconds=0,timed_out=False,hardware_programmed=False,timing_signed_off=False,
        motion_release_allowed=False,route_option=1,place_option=1,pnr_timeout_seconds=args.timeout,
        pnr_driver_sha256=sha(__file__),pnr_tcl_sha256=sha(tcl),synthesis_netlist_before_pnr_sha256=expected)
    save(record);timed_out=False
    with (OUT/'build.log').open('w',encoding='utf-8') as log:
        tool=subprocess.Popen(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
        record['gowin_pid']=tool.pid;save(record)
        try:rc=tool.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:tool.kill();tool.wait();timed_out=True;rc=-1
        except KeyboardInterrupt:tool.terminate();tool.wait();rc=130
    text=(OUT/'build.log').read_text(encoding='utf-8',errors='replace')
    changed=any(not Path(p).is_file() or sha(p)!=h for p,h in inputs.items())
    actual=sha(netlist)
    reused=actual==expected and 'GowinSynthesis start' not in text
    rebuilt=('GowinSynthesis finish' in text and netlist.stat().st_mtime>=started)
    bitstream=OUT/'impl/pnr/a741.fs';report=OUT/'impl/pnr/a741.tr'
    passed=rc==0 and not changed and (reused or rebuilt) and bitstream.is_file() and bitstream.stat().st_mtime>=started and not re.search(r'(?m)^\s*(ERROR|FATAL)',text)
    record.update(returncode=rc,timed_out=timed_out,seconds=time.time()-started,sources_changed=changed,
        synthesis_reused=reused,tool_auto_resynthesized=rebuilt,synthesis_netlist_sha256=actual,
        compile_passed=passed,run_state='timed_out' if timed_out else 'completed' if passed else 'failed',
        timing_violations={},worst_reported_slack_ns={},clock_frequencies={},minimum_pulse_width_worst_slack_ns=None)
    synth_report=OUT/'impl/gwsynthesis/a741_syn.rpt.html'
    if rebuilt and synth_report.is_file() and synth_report.stat().st_mtime>=started:
        record['synthesis_timing']=synthesis_timing(synth_report)
        record['synthesis_report_sha256']=sha(synth_report)
    if report.is_file() and report.stat().st_mtime>=started:
        timing=report.read_text(encoding='utf-8',errors='replace')
        record['timing_report_sha256']=sha(report)
        record['timing_violations']={k.lower():int(v) for k,v in re.findall(r'<Numbers of (Setup|Hold|Recovery|Removal) Violated Endpoints>:(\d+)',timing)}
        record['minimum_pulse_width_worst_slack_ns']=pulse_width_slack(timing)
        for kind in ('Setup','Hold','Recovery','Removal'):
            match=re.search(kind+r' Paths Table\n<Report Command>:[^\n]*\n(.*?)(?=\n3\.)',timing,re.S)
            if match:
                slacks=re.findall(r'(?m)^\s*\d+\s+(-?\d+\.\d+)\s+',match[1])
                if slacks:record['worst_reported_slack_ns'][kind.lower()]=min(map(float,slacks))
        table=re.search(r'2\.3 Max Frequency Summary\n(.*?)\n2\.4',timing,re.S)
        if table:
            for clock,requested,actual_mhz in re.findall(r'(?m)^\s*\d+\s+(\S+)\s+(\d+\.\d+)\(MHz\)\s+(\d+\.\d+)\(MHz\)',table[1]):
                record['clock_frequencies'][clock]={'constraint_mhz':float(requested),'reported_fmax_mhz':float(actual_mhz)}
    if passed:record.update(artifact=str(bitstream),artifact_sha256=sha(bitstream))
    save(record)
    for name in ('result.json','build.log','verified-pnr.tcl'):
        shutil.copy2(OUT/name,EVIDENCE/name)
    print(json.dumps({k:record[k] for k in ('compile_passed','run_state','seconds','synthesis_reused','timing_violations','worst_reported_slack_ns')},indent=2))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
