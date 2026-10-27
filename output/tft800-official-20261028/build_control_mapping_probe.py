"""Compare DE/BL input roles at unchanged clock, raster, RGB and sync pins."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, time
BASE=Path(__file__).resolve().parent
SRC=BASE/'interface-probe'
OUT=BASE/'control-mapping-probe'
OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
w=(SRC/'wrapper.v').read_text()
w=w.replace('module official_probe(', 'module official_probe #(parameter MODE_FRAMES=480)(')
w=w.replace('always @(negedge pclk) pins<={de,hs,vs,rgb};', '''reg [1:0] mode=0;
 reg [8:0] mode_frames=0;
 (* syn_preserve=1, syn_keep=1 *) reg pin_de=0,pin_bl=0;
 // AB21/AB22 are documented module inputs. Only their digital waveform
 // changes. No connector/power/clock/RGB/HS/VS pins are reassigned.
 always @(negedge pclk) begin
  pins<={de,hs,vs,rgb};
  case(mode)
   0:begin pin_de<=de;pin_bl<=1;end
   1:begin pin_de<=1;pin_bl<=de;end
   default:begin pin_de<=de;pin_bl<=de;end
  endcase
 end''')
w=w.replace('.I(pins[18])', '.I(pin_de)').replace('.I(sys_count[25])', '.I(pin_bl)')
w=w.replace('else begin old_vs<=vs;if(vs && !old_vs) frames<=frames+1\'b1;end', '''else begin old_vs<=vs;if(vs && !old_vs) frames<=frames+1'b1;end
 always @(posedge pclk or negedge reset_n)
  if(!reset_n) begin mode<=0;mode_frames<=0;end
  else if(vs && !old_vs) begin
   if(mode_frames==MODE_FRAMES-1) begin
    mode_frames<=0;
    if(mode==2) mode<=0;else mode<=mode+1'b1;
   end else mode_frames<=mode_frames+1'b1;
  end''')
w=w.replace("assign led={2'b00,seen_de", "assign led={mode,seen_de")
(OUT/'wrapper.v').write_text(w)
for name in ('probe.gprj','probe.cst','probe.sdc','build.tcl'):
    shutil.copy2(SRC/name,OUT/name)
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A729','0000A72B'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
    r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,
 'sources_changed':False,'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,
 'purpose':'3 modes, 480 frames ~8.064s each: documented DE/BL, swapped DE/BL, DE on both; no power pin changes'},indent=2)+'\n')
review=(BASE/'review_interface_probe.py').read_text().replace("/'interface-probe'", " / 'control-mapping-probe'")
review=review.replace("p['O'] in ('TFT_clk','TFT_pwm')", "p['O']=='TFT_clk'")
review=review.replace('assert len(windows)==19', 'assert len(windows)==20')
review=review.replace("'backlight_toggle_seconds':2**25/50000000,", "'mapping_mode_frames':480,'mapping_mode_seconds':480*1056*525/33000000,")
(BASE/'review_control_mapping_probe.py').write_text(review)
with (OUT/'review-console.log').open('w') as log:
    subprocess.run([sys.executable,'-X','utf8',str(BASE/'review_control_mapping_probe.py')],check=True,stdout=log)
print('PASS control mapping build and STA/SDF including both possible DE pins',sha(OUT/'impl/pnr/probe.fs'))
