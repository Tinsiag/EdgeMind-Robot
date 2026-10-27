from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time
BASE=Path(__file__).resolve().parent
SRC=BASE/'interface-probe';OUT=BASE/'rotation-probe-v2';OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
shutil.copy2(BASE/'rotation_scan.v',OUT/'src/rotation_scan.v')
w=(SRC/'wrapper.v').read_text()
w=w.replace('module official_probe(', 'module official_probe #(parameter MODE_FRAMES=480)(')
w=w.replace('tft_ctrl_test official(', 'wire portrait;\n rotation_scan #(.MODE_FRAMES(MODE_FRAMES)) official(')
w=w.replace('.TFT_de(de),.TFT_pwm(pwm)', '.TFT_de(de),.TFT_pwm(pwm),.portrait(portrait)')
w=w.replace('.I(sys_count[25])', '.I(pwm)')
w=w.replace("assign led={2'b00,seen_de", "assign led={1'b0,portrait,seen_de")
(OUT/'wrapper.v').write_text(w)
for name in ('probe.gprj','probe.cst','probe.sdc','build.tcl'):shutil.copy2(SRC/name,OUT/name)
(OUT/'probe.gprj').write_text((OUT/'probe.gprj').read_text().replace('src/tft_ctrl_test.v','src/rotation_scan.v'))
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A729','0000A72C'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,'purpose':'user-requested clockwise90 comparison: rotated pattern800x480 and transposed480x800 raster, each480frames'},indent=2)+'\n')
review=(BASE/'review_interface_probe.py').read_text().replace("/'interface-probe'", " / 'rotation-probe-v2'")
review=review.replace("'official_scanner_pll_colors_unchanged':True", "'official_pll_unchanged':True,'scanner_replaced_for_user_rotation_comparison':True,'portrait_timing_panel_compatibility_unverified':True")
review=review.replace("'backlight_toggle_seconds':2**25/50000000,", "'backlight_blinks':False,'rotation_clockwise_degrees':90,'mode_frames':480,'mode_seconds':8.064,")
(BASE/'review_rotation_probe.py').write_text(review)
with (OUT/'review-console.log').open('w') as log:
 subprocess.run([sys.executable,'-X','utf8',str(BASE/'review_rotation_probe.py')],check=True,stdout=log)
print('PASS clockwise rotation build/STA/pad-SDF',sha(OUT/'impl/pnr/probe.fs'))
