"""Return to the observed rolling-block candidate, change PCLK polarity only."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time
BASE=Path(__file__).resolve().parent;SRC=BASE/'control-mapping-probe';OUT=BASE/'falling-sample-probe';OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
original=(SRC/'wrapper.v').read_text()
w=original.replace('clock_pad(.IO(TFT_clk),.I(pclk)', 'clock_pad(.IO(TFT_clk),.I(~pclk)')
assert w!=original and w.count('.I(~pclk)')==1
(OUT/'wrapper.v').write_text(w)
for name in ('probe.gprj','probe.cst','probe.sdc','build.tcl'):shutil.copy2(SRC/name,OUT/name)
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A72B','0000A72E'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,
 'parent_visible_response_bitstream_sha256':'14ebf7bd68522b0cc13a710f325d5a1ecde147afd3766c53f35affc7dd32b22f',
 'sole_rtl_change':'invert PCLK at output; data launch unchanged, falling external edge centered in stable interval'},indent=2)+'\n')
# Reviewer is versioned separately: supports actual LUT1 inversion and uses
# same-run STA bounds when Gowin omits split-inverter clock SDF connections.
with (OUT/'review-console.log').open('w') as log:
 subprocess.run([sys.executable,'-X','utf8',str(BASE/'review_falling_sample_probe.py')],check=True,stdout=log)
print('PASS polarity-only probe build/STA/falling sample SDF',sha(OUT/'impl/pnr/probe.fs'))
