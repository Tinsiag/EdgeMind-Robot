"""Backlight blink + physical pad input readback; no hardware operation."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,time
BASE=Path(__file__).resolve().parent
SRC=BASE/'official-probe-v3'
OUT=BASE/'interface-probe'
OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
wrapper=(SRC/'wrapper.v').read_text()
wrapper=wrapper.replace('output wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm','output wire TFT_hs,TFT_vs,inout wire TFT_clk,TFT_de,TFT_pwm')
wrapper=wrapper.replace('assign {TFT_de,TFT_hs,TFT_vs,TFT_rgb}=pins;', 'assign {TFT_hs,TFT_vs,TFT_rgb}=pins[17:0];')
wrapper=wrapper.replace('assign TFT_clk=pclk;assign TFT_pwm=pwm;', '''wire read_clk,read_de,read_bl;
 IOBUF clock_pad(.IO(TFT_clk),.I(pclk),.OEN(1'b0),.O(read_clk));
 IOBUF de_pad(.IO(TFT_de),.I(pins[18]),.OEN(1'b0),.O(read_de));
 IOBUF bl_pad(.IO(TFT_pwm),.I(sys_count[25]),.OEN(1'b0),.O(read_bl));
 (* ASYNC_REG="TRUE" *) reg [1:0] read_clk_sync,read_de_sync,read_bl_sync;
 reg read_clk_old=0,seen_de=0;reg [23:0] edge_count=0;
 always @(posedge clk50M or negedge reset_n)
  if(!reset_n) begin read_clk_sync<=0;read_de_sync<=0;read_bl_sync<=0;read_clk_old<=0;edge_count<=0;seen_de<=0;end
  else begin
   read_clk_sync<={read_clk_sync[0],read_clk};read_de_sync<={read_de_sync[0],read_de};read_bl_sync<={read_bl_sync[0],read_bl};
   read_clk_old<=read_clk_sync[1];if(read_clk_sync[1] && !read_clk_old) edge_count<=edge_count+1'b1;
   if(read_de_sync[1]) seen_de<=1;
  end''')
wrapper=wrapper.replace("assign led={5'b00000,frames[4],sys_count[24],1'b1};", "assign led={2'b00,seen_de,edge_count[22],read_bl_sync[1],frames[4],sys_count[24],1'b1};")
(OUT/'wrapper.v').write_text(wrapper)
for name in ('probe.gprj','probe.cst','probe.sdc','build.tcl'):
 shutil.copy2(SRC/name,OUT/name)
with (OUT/'probe.sdc').open('a') as f:
 f.write('set_max_delay 10 -to [get_pins {read_clk_sync_0_s0/D read_de_sync_0_s0/D read_bl_sync_0_s0/D}]\n')
 f.write('set_false_path -hold -to [get_pins {read_clk_sync_0_s0/D read_de_sync_0_s0/D read_bl_sync_0_s0/D}]\n')
# The de/clock/backlight output endpoints are now physical IOBUFs. Keep the
# previous output maximum and inspect all three input samplers explicitly.
text=(OUT/'build.tcl').read_text().replace('0000A728','0000A729')
(OUT/'build.tcl').write_text(text)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
started=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0
assert all(sha(OUT/n)==h for n,h in hashes.items())
result={'returncode':r.returncode,'seconds':time.time()-started,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,'purpose':'backlight1.342s on/off plus PCLK/DE/backlight pad readback LEDs, official eight colour blocks'}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS interface probe built; review before programming',result['artifact_sha256'])
