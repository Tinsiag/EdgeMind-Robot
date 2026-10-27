from pathlib import Path
import hashlib,json,subprocess
BASE=Path(__file__).resolve().parent;P=BASE/'rotation-swapped-probe'
tb=(BASE/'rotation_probe_tb.v').read_text()
# Keep the same inverse-coordinate full-frame checker; observe physical
# AB21 as DE and AB22 as the constant high control in this candidate.
tb=tb.replace('TFT_de','__DATA_ENABLE_PAD__').replace('TFT_pwm','TFT_de').replace('__DATA_ENABLE_PAD__','TFT_pwm')
tb=tb.replace('official_probe #(.MODE_FRAMES(3)) dut(.*);','official_probe #(.MODE_FRAMES(3)) dut(.*);')
tb=tb.replace(' || !led[3]', '')
tb=tb.replace('constant BL,actual IOBUF','swapped DE onAB21 and highAB22,actual IOBUF')
tbfile=P/'rotation_swapped_tb.v';tbfile.write_text(tb)
lib=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
files=[tbfile,P/'wrapper.v',P/'src/rotation_scan.v',lib]
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in files}
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','iverilog','-g2012','-s','rotation_probe_tb','-o','/var/tmp/edgemind-rotation-swapped.vvp',*map(linux,files)],capture_output=True)
(P/'simulation-compile.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','vvp','/var/tmp/edgemind-rotation-swapped.vvp'],capture_output=True,timeout=90)
(P/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and b'PASS' in r.stdout,r.stdout.decode(errors='replace')
assert all(sha(Path(p))==h for p,h in hashes.items())
(P/'SIMULATION.json').write_text(json.dumps({'passed':True,'input_sha256':hashes,'pll_model':'ideal33MHz; actual Gowin IOBUF model',
 'mode_duration':'accelerated480 to3 frames; unchanged pixel/line/frame timing','checks':'same inverse-coordinate checker but DE observed atAB21 and AB22 constantly high'},indent=2)+'\n')
print(r.stdout.decode())
