from pathlib import Path
import hashlib,json,subprocess
BASE=Path(__file__).resolve().parent
P=BASE/'control-mapping-probe'
lib=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
files=[BASE/'control_mapping_tb.v',P/'wrapper.v',P/'src/disp_driver.v',P/'src/tft_ctrl_test.v',lib]
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in files+[P/'src/disp_parameter_cfg.v']}
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','iverilog','-g2012','-s','control_mapping_tb','-I'+linux(P/'src'),'-o','/var/tmp/edgemind-control-mapping.vvp',*map(linux,files)],capture_output=True)
(P/'simulation-compile.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','vvp','/var/tmp/edgemind-control-mapping.vvp'],capture_output=True,timeout=90)
(P/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and b'PASS' in r.stdout,r.stdout.decode(errors='replace')
assert all(sha(Path(p))==h for p,h in hashes.items())
(P/'SIMULATION.json').write_text(json.dumps({'passed':True,'input_sha256':hashes,'pll_model':'ideal 33MHz; actual Gowin IOBUF model','mode_duration':'accelerated from480 to3 frames; unchanged raster'},indent=2)+'\n')
print(r.stdout.decode())
