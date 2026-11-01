"""Run the hardware-free RTL checks with ModelSim.

Mirrors scripts/check.py's source list and PASS criterion. Added because the
Ubuntu WSL distribution that check.py shells out to is no longer installed on
this machine; the Verilog sources and benches are unchanged.
"""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MSIM=Path(os.environ.get('MODELSIM_BIN',r'F:\modeltech64_10.6d\win64'))
PRIM=Path(os.environ.get('GOWIN_HOME',r'F:\Gowin\Gowin_V1.9.12_x64'))/'IDE/simlib/gw5a/prim_sim.v'

def sources():
 eth=ROOT.parent/'third_party/verilog-ethernet/rtl'
 return ([p for p in sorted((ROOT/'rtl').glob('*.v')) if p.name!='a745_top.v']
  +sorted((ROOT/'lib').glob('*.v'))+sorted((ROOT/'vendor').glob('*.v'))
  +[eth/n for n in ['axis_async_fifo.v','axis_gmii_tx.v','lfsr.v']])

def run(cmd,cwd,timeout=600):
 p=subprocess.run([str(MSIM/cmd[0])]+cmd[1:],cwd=cwd,capture_output=True,text=True,errors='replace',timeout=timeout)
 return p.returncode,p.stdout+p.stderr

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--only',action='append');ap.add_argument('--plusarg',action='append',default=[])
 args=ap.parse_args();out=ROOT/'.local/msim-check';out.mkdir(parents=True,exist_ok=True)
 benches=sorted((ROOT/'tests').glob('*_tb.v'))
 if args.only:benches=[p for p in benches if p.stem in args.only]
 assert benches,'No selected tests'
 inputs=sources()+benches;hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 rc,log=run(['vlib.exe','work'],out);(out/'vlib.log').write_text(log,encoding='utf-8')
 compile_sources=[str(p) for p in sources()]
 if PRIM.is_file():compile_sources.append(str(PRIM))
 rc,log=run(['vlog.exe','-sv','-quiet','-work','work']+compile_sources,out,timeout=900)
 (out/'sources-compile.log').write_text(log,encoding='utf-8')
 if rc:raise RuntimeError('source compile failed\n'+log[-4000:])
 results={};started=time.monotonic()
 for bench in benches:
  name=bench.stem
  rc,log=run(['vlog.exe','-sv','-quiet','-work','work',str(bench)],out,timeout=600)
  (out/(name+'-compile.log')).write_text(log,encoding='utf-8')
  if rc:results[name]={'phase':'compile','passed':False,'log':log[-2000:]};continue
  cmd=['vsim.exe','-c','-quiet','-work','work',name]+list(args.plusarg)+['-do','run -all; quit -f']
  try:rc,log=run(cmd,out,timeout=900)
  except subprocess.TimeoutExpired:results[name]={'phase':'execute','passed':False,'log':'timeout'};continue
  (out/(name+'.log')).write_text(log,encoding='utf-8')
  fatal=bool(re.search(r'(?m)^# \*\* (Error|Fatal)',log))
  passed=rc==0 and 'PASS' in log and not fatal
  results[name]={'phase':'execute','passed':passed,
   'log':'' if passed else log[-2000:],
   'summary':'; '.join(l[2:] for l in log.splitlines() if re.search(r'PASS|FAIL|Error|Fatal',l))[:400]}
  print(('PASS ' if passed else 'FAIL ')+name+' '+results[name].get('summary',''),flush=True)
 unchanged=hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 record={'tool':'modelsim','modelsim_bin':str(MSIM),'seconds':time.monotonic()-started,
  'inputs_unchanged_during_tests':unchanged,'source_sha256':hashes,'results':results,
  'passed':[k for k,v in results.items() if v['passed']],'failed':[k for k,v in results.items() if not v['passed']]}
 (out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in record.items() if k not in ('source_sha256','results')},indent=2))
 if record['failed'] or not unchanged:raise SystemExit(1)
if __name__=='__main__':main()
