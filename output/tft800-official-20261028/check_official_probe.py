from pathlib import Path
import subprocess,json,hashlib
OUT=Path(__file__).resolve().parent
P=OUT/'official-probe-v3'
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
files=[OUT/'official_probe_tb.v',P/'wrapper.v',P/'src/disp_driver.v',P/'src/tft_ctrl_test.v',P/'src/disp_parameter_cfg.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in files}
cmd=['wsl','-d','Ubuntu-26.04','--exec','iverilog','-g2012','-s','official_probe_tb','-I'+linux(P/'src'),'-o','/var/tmp/edgemind-official-probe.vvp',*[linux(p) for p in files[:-1]]]
r=subprocess.run(cmd,capture_output=True)
(P/'simulation-compile.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','vvp','/var/tmp/edgemind-official-probe.vvp'],capture_output=True,timeout=60)
(P/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and b'PASS' in r.stdout,r.stdout.decode(errors='replace')
assert all(sha(Path(p))==h for p,h in hashes.items())
(P/'SIMULATION.json').write_text(json.dumps({'passed':True,'pll_replaced_by_ideal33mhz_in_simulation':True,'inputs':hashes},indent=2)+'\n')
print(r.stdout.decode(errors='replace'))
