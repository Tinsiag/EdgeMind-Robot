from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time
BASE=Path(__file__).resolve().parent;SRC=BASE/'rotation-probe-v2';OUT=BASE/'rotation-swapped-probe';OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
w=(SRC/'wrapper.v').read_text()
w=w.replace('de_pad(.IO(TFT_de),.I(pins[18])','de_pad(.IO(TFT_de),.I(pwm)')
w=w.replace('bl_pad(.IO(TFT_pwm),.I(pwm)','bl_pad(.IO(TFT_pwm),.I(pins[18])')
assert w!=(SRC/'wrapper.v').read_text()
(OUT/'wrapper.v').write_text(w)
for name in ('probe.gprj','probe.cst','probe.sdc','build.tcl'):shutil.copy2(SRC/name,OUT/name)
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A72C','0000A72D'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,'purpose':'user-requested DE/BL swap applied to exactly same clockwise90 dualgeometry candidate'},indent=2)+'\n')
review=(BASE/'review_rotation_probe.py').read_text().replace(" / 'rotation-probe-v2'", " / 'rotation-swapped-probe'")
review=review.replace("p['O'] in ('TFT_clk','TFT_pwm')", "p['O'] in ('TFT_clk','TFT_de')")
review=review.replace("'backlight_blinks':False", "'AB21_driven_with_DE':True,'AB22_driven_high':True,'diagnostic_DE_BL_swap':True")
(BASE/'review_rotation_swapped_probe.py').write_text(review)
with (OUT/'review-console.log').open('w') as log:
 subprocess.run([sys.executable,'-X','utf8',str(BASE/'review_rotation_swapped_probe.py')],check=True,stdout=log)
print('PASS rotation with DE/BL swapped build/STA/pad-SDF',sha(OUT/'impl/pnr/probe.fs'))
