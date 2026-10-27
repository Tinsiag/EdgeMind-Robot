"""Resolution hypothesis using the ACG720 chapter28 HW_TFT43 branch."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,time
BASE=Path(__file__).resolve().parent;SRC=BASE/'falling-sample-probe';OUT=BASE/'official480-9mhz-probe';OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
for name in ('wrapper.v','probe.gprj','probe.cst','probe.sdc','build.tcl'):shutil.copy2(SRC/name,OUT/name)
cfg=OUT/'src/disp_parameter_cfg.v'
t=cfg.read_text();assert '\n//`define HW_TFT43' in t and '\n`define HW_TFT50' in t
cfg.write_text(t.replace('\n//`define HW_TFT43','\n`define HW_TFT43').replace('\n`define HW_TFT50','\n//`define HW_TFT50'))
# Color-block geometry follows the documented active area,4 equal rows and2 columns.
top=OUT/'src/tft_ctrl_test.v';t=top.read_text()
for a,b in ((480,272),(360,204),(240,136),(120,68),(800,480),(400,240)):
 t=re.sub(r'\b'+str(a)+r'\b',str(b),t)
top.write_text(t)
pll=OUT/'src/gowin_pll/gowin_pll_mod.v';t=pll.read_text()
assert 'MDIV_SEL = 33;' in t and 'ODIV0_SEL = 25;' in t
pll.write_text(t.replace('MDIV_SEL = 33;','MDIV_SEL = 36;').replace('ODIV0_SEL = 25;','ODIV0_SEL = 100;'))
pll=OUT/'src/gowin_pll/gowin_pll.v';t=pll.read_text();assert 'MULTI_FAC = 33;' in t
pll.write_text(t.replace('MULTI_FAC = 33;','MULTI_FAC = 36;'))
# 50MHz/2*36=900MHz VCO; /100 gives9MHz and a50% duty cycle.
(OUT/'probe.sdc').write_text((OUT/'probe.sdc').read_text().replace('lcd33m','lcd9m').replace('-multiply_by 33 -divide_by 50','-multiply_by 9 -divide_by 50'))
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A72E','0000A72F'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,'active_size':[480,272],'total_size':[525,286],'pixel_clock_mhz':9,
 'basis':'ACG720 chapter28 HW_TFT43 timing branch; same rolling-response wrapper, invertedPCLK, mapping modes and motor GND',
 'pll':'same vendor initialization, VCO50/2*36=900MHz, output900/100=9MHz'},indent=2)+'\n')
review=(BASE/'review_falling_sample_probe.py').read_text().replace(" / 'falling-sample-probe'", " / 'official480-9mhz-probe'").replace('lcd33m','lcd9m').replace('1000/66','1000/18')
review=review.replace("'official_scanner_pll_colors_unchanged':True", "'official_scanner_unchanged':True,'official_HW_TFT43_branch_selected':True,'pll_output_mhz':9,'active_size':[480,272],'color_geometry_adapted':True")
review=review.replace("'polarity_only_rtl_change':True", "'resolution_hypothesis_trial':True")
review=review.replace('480*1056*525/33000000','480*525*286/9000000')
(BASE/'review_official480_9_probe.py').write_text(review)
with (OUT/'review-console.log').open('w') as log:
 subprocess.run([sys.executable,'-X','utf8',str(BASE/'review_official480_9_probe.py')],check=True,stdout=log)
print('PASS official HW_TFT43 raster9MHz build/STA/falling-edge pad review',sha(OUT/'impl/pnr/probe.fs'))
