from pathlib import Path
import hashlib,json,re,subprocess
BASE=Path(__file__).resolve().parent;P=BASE/'official480-9mhz-probe'
tb=(BASE/'control_mapping_tb.v').read_text().replace('if(TFT_clk!==0)','if(TFT_clk!==1)').replace('always @(posedge TFT_clk)','always @(negedge TFT_clk)')
tb=tb.replace('15.151515','55.555556').replace('<15.15','<55.55')
# Apply whole-number replacements in a single pass to avoid cascading480/272.
mapping={'800':'480','480':'272','797':'477','477':'269','400':'240','120':'68'}
tb=re.sub(r'\b(?:800|480|797|477|400|120)\b',lambda m:mapping[m[0]],tb)
tb=tb.replace('800x480/33MHz','480x272/9MHz').replace('half-cycle output timing','falling-edge half-cycle output timing')
tbfile=P/'official480_9_tb.v';tbfile.write_text(tb)
lib=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
files=[tbfile,P/'wrapper.v',P/'src/disp_driver.v',P/'src/tft_ctrl_test.v',lib]
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in files+[P/'src/disp_parameter_cfg.v']}
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','iverilog','-g2012','-s','control_mapping_tb','-I'+linux(P/'src'),'-o','/var/tmp/edgemind-official480-9.vvp',*map(linux,files)],capture_output=True)
(P/'simulation-compile.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','vvp','/var/tmp/edgemind-official480-9.vvp'],capture_output=True,timeout=90)
(P/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and b'PASS' in r.stdout,r.stdout.decode(errors='replace')
assert all(sha(Path(p))==h for p,h in hashes.items())
(P/'SIMULATION.json').write_text(json.dumps({'passed':True,'input_sha256':hashes,'pll_model':'ideal9MHz, actual Gowin IOBUF model',
 'mode_duration':'accelerated480 to3 frames; same pixel/line/frame timing','sample_edge_hypothesis':'falling',
 'checks':'all3control-mapping modes, full480x272 active frames, all8colour blocks, clock edge setup, physical pad readback and motorGND'},indent=2)+'\n')
print(r.stdout.decode())
