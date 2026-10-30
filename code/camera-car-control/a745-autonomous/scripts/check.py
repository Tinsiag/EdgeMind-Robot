"""Execute the hardware-free RTL checks of the new single profile."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sources():
 eth=ROOT.parent/'third_party/verilog-ethernet/rtl'
 return [p for p in sorted((ROOT/'rtl').glob('*.v')) if p.name!='a745_top.v']+sorted((ROOT/'lib').glob('*.v'))+sorted((ROOT/'vendor').glob('*.v'))+[eth/n for n in ['axis_async_fifo.v','axis_gmii_tx.v','lfsr.v']]
def linux(p):
 s=Path(p).resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--only',action='append');args=ap.parse_args();out=ROOT/'.local/tests';out.mkdir(parents=True,exist_ok=True);passed=[]
 benches=sorted((ROOT/'tests').glob('*_tb.v'))
 if args.only:benches=[p for p in benches if p.stem in args.only]
 assert benches,'No selected tests';inputs=sources()+benches;hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 for bench in benches:
  name=bench.stem;product=out/(name+'.vvp');prefix=['wsl.exe','-d','Ubuntu-26.04','--cd',linux(ROOT),'--exec']
  if name=='camera_tft800_tb':
   obj='/var/tmp/edgemind-a745-'+name
   cmd=prefix+['verilator','--binary','--timing','-j','4','-Wno-fatal','--Mdir',obj,'--top-module',name,*map(linux,sources()),linux(bench)]
   execute=prefix+[obj+'/V'+name]
  else:
   primitive=[linux(Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v'))] if name=='camera_pads_tb' else []
   cmd=prefix+['iverilog','-g2012','-s',name,'-o',linux(product),*map(linux,sources()),*primitive,linux(bench)]
   execute=prefix+['vvp',linux(product)]
  p=subprocess.run(cmd,capture_output=True,text=True,errors='replace');(out/(name+'-compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
  if p.returncode:raise RuntimeError(p.stdout+p.stderr)
  p=subprocess.run(execute,capture_output=True,text=True,errors='replace',timeout=90);(out/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout.strip(),flush=True)
  if p.returncode or 'PASS' not in p.stdout:raise RuntimeError(p.stdout+p.stderr)
  passed.append(name)
 assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'Inputs changed during tests'
 (out/'result.json').write_bytes((json.dumps({'passed':passed,'input_sha256':hashes,'hardware_tested':False,'unix_time':time.time()},indent=2)+'\n').encode())
if __name__=='__main__':main()
