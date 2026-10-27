"""One-variable follow-up: retain pad/scanner configuration, stop BL blinking."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, time

BASE = Path(__file__).resolve().parent
SRC = BASE/'interface-probe'
OUT = BASE/'interface-steady-probe'
OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src', OUT/'src', dirs_exist_ok=True)
wrapper = (SRC/'wrapper.v').read_text()
wrapper = wrapper.replace('IOBUF bl_pad(.IO(TFT_pwm),.I(sys_count[25])', '''// One 200ms startup delay, then continuously on; never blink or wrap.
 reg [23:0] startup_count=0;
 wire backlight_on=startup_count==24'd10000000;
 always @(posedge clk50M or negedge reset_n)
  if(!reset_n) startup_count<=0;
  else if(!backlight_on) startup_count<=startup_count+1'b1;
 IOBUF bl_pad(.IO(TFT_pwm),.I(backlight_on)''')
assert wrapper != (SRC/'wrapper.v').read_text()
(OUT/'wrapper.v').write_text(wrapper)
for name in ('probe.gprj', 'probe.cst', 'probe.sdc', 'build.tcl'):
    shutil.copy2(SRC/name, OUT/name)
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A729', '0000A72A'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = [p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v', '.sdc', '.cst', '.gprj', '.tcl')]
hashes = {str(p.relative_to(OUT)): sha(p) for p in inputs}
start = time.time()
with (OUT/'build.log').open('w', encoding='utf-8') as log:
    r = subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe', str(OUT/'build.tcl')], cwd=OUT, stdout=log, stderr=subprocess.STDOUT, timeout=300)
assert r.returncode == 0
assert all(sha(OUT/p) == h for p, h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode': r.returncode, 'seconds': time.time()-start,
    'source_sha256': hashes, 'sources_changed': False, 'artifact_sha256': sha(OUT/'impl/pnr/probe.fs'),
    'hardware_programmed': False, 'purpose': 'Same IOBUF/scanner as visible colour-block build; BL on after 200ms and remains on'}, indent=2)+'\n')
review = (BASE/'review_interface_probe.py').read_text().replace("/'interface-probe'", " / 'interface-steady-probe'")
review = review.replace("'backlight_toggle_seconds':2**25/50000000,", "'backlight_startup_seconds':0.2,'backlight_blinks':False,")
(BASE/'review_steady_probe.py').write_text(review)
subprocess.run([sys.executable, '-X', 'utf8', str(BASE/'review_steady_probe.py')], check=True, stdout=(OUT/'review-console.log').open('w'))
tb = (SRC/'interface_probe_tb.v').read_text()
tb = tb.replace("force dut.sys_count=26'd0;#200;", '#200;')
tb = tb.replace("force dut.sys_count=26'h2000000;#200;", "@(negedge clk50M);force dut.startup_count=24'd9999998;#20;release dut.startup_count;#200;")
tb = tb.replace('release dut.sys_count;', '')
tb = tb.replace('if({left_in1,left_in2,right_in1,right_in2}!==0)', "if({left_in1,left_in2,right_in1,right_in2}!==0 || !TFT_pwm || !led[3] || !dut.backlight_on)")
tb = tb.replace('backlight toggle', 'backlight stays on after startup')
tbfile = OUT/'steady_probe_tb.v'
tbfile.write_text(tb)
lib = Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
files = [tbfile, OUT/'wrapper.v', OUT/'src/disp_driver.v', OUT/'src/tft_ctrl_test.v', lib]
def linux(p):
    s = p.resolve().as_posix()
    return '/mnt/'+s[0].lower()+s[2:]
sim_hash = {str(p):sha(p) for p in files+[OUT/'src/disp_parameter_cfg.v']}
r = subprocess.run(['wsl', '-d', 'Ubuntu-26.04', '--exec', 'iverilog', '-g2012', '-s', 'official_probe_tb', '-I'+linux(OUT/'src'), '-o', '/var/tmp/edgemind-steady-probe.vvp', *map(linux, files)], capture_output=True)
(OUT/'simulation-compile.log').write_bytes(r.stdout+r.stderr)
assert r.returncode == 0
r = subprocess.run(['wsl', '-d', 'Ubuntu-26.04', '--exec', 'vvp', '/var/tmp/edgemind-steady-probe.vvp'], capture_output=True, timeout=60)
(OUT/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode == 0 and b'PASS' in r.stdout, r.stdout.decode(errors='replace')
assert all(sha(Path(p)) == h for p,h in sim_hash.items())
(OUT/'SIMULATION.json').write_text(json.dumps({'passed':True, 'input_sha256':sim_hash, 'pll_model':'ideal33MHz; Gowin actual IOBUF model', 'startup_test':'counter advanced near 200ms threshold; BL stays on for two frames'}, indent=2)+'\n')
print(r.stdout.decode())
print('PASS steady probe build/simulation/STA/SDF; no hardware write', sha(OUT/'impl/pnr/probe.fs'))
