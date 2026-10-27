from pathlib import Path
import hashlib,json,re,subprocess,sys
BASE=Path(__file__).resolve().parent
P=BASE/'interface-probe'
src=(BASE/'review_official_probe.py').read_text()
src=src.replace("/'official-probe-v3'","/'interface-probe'")
src=src.replace("clkbuf='TFT_clk_obuf'", "clkbuf='clock_pad'")
src=src.replace("arc(clkbuf,'I','O')", "arc(clkbuf,'I','IO')")
src=src.replace("windows={};paths={}",'''pad_inputs={}
for name,net,ff in (('clock_pad','read_clk','read_clk_sync_0_s0'),('de_pad','read_de','read_de_sync_0_s0'),('bl_pad','read_bl','read_bl_sync_0_s0')):
 assert logic[name][0]=='IOBUF' and logic[name][1]['OEN']=='GND'
 assert logic[name][1]['O']==net==logic[ff][1]['D']
 pad_inputs[name]={'input_net':net,'first_sampler':ff}
 # Normalize the pad endpoint name for the existing output audit only.
 logic[name][1]['O']=logic[name][1]['IO']
windows={};paths={}''')
src=src.replace("if kind!='OBUF'", "if kind not in ('OBUF','IOBUF')")
src=src.replace("arc(buf,'I','O')", "arc(buf,'I','IO' if logic[buf][0]=='IOBUF' else 'O')")
src=src.replace("'motor_pads_grounded':True,", "'motor_pads_grounded':True,'pad_input_buffers_verified':pad_inputs,'backlight_toggle_seconds':2**25/50000000,")
review=BASE/'review_interface_probe.py';review.write_text(src)
subprocess.run([sys.executable,'-X','utf8',str(review)],check=True)

tb=(BASE/'official_probe_tb.v').read_text().replace('official_probe dut(.*);','GSR GSR(.GSRI(1\'b1));\n official_probe dut(.*);')
tb=tb.replace("if({left_in1,left_in2,right_in1,right_in2}!==0 || !TFT_pwm)", "if({left_in1,left_in2,right_in1,right_in2}!==0)")
tb=tb.replace('integer x=0', '''initial begin
 wait(reset_n);#500;
 force dut.sys_count=26'd0;#200;
 if(TFT_pwm!==0 || led[3]!==0) $fatal(1,"BL low/readback");
 force dut.sys_count=26'h2000000;#200;
 if(TFT_pwm!==1 || led[3]!==1) $fatal(1,"BL high/readback");
 release dut.sys_count;
 #2000000;
 if(dut.edge_count<100 || !led[5]) $fatal(1,"Missing PCLK/DE pad readback count=%d de=%b",dut.edge_count,led[5]);
end
integer x=0''')
tb=tb.replace('PASS official800x480', 'PASS physicalIOBUF readback and backlight toggle plus official800x480')
tbfile=P/'interface_probe_tb.v';tbfile.write_text(tb)
lib=Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
files=[tbfile,P/'wrapper.v',P/'src/disp_driver.v',P/'src/tft_ctrl_test.v',lib]
def linux(p):
 s=p.resolve().as_posix();return '/mnt/'+s[0].lower()+s[2:]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in files+[P/'src/disp_parameter_cfg.v']}
cmd=['wsl','-d','Ubuntu-26.04','--exec','iverilog','-g2012','-s','official_probe_tb','-I'+linux(P/'src'),'-o','/var/tmp/edgemind-interface-probe.vvp',*[linux(p) for p in files]]
r=subprocess.run(cmd,capture_output=True);(P/'simulation-compile.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
r=subprocess.run(['wsl','-d','Ubuntu-26.04','--exec','vvp','/var/tmp/edgemind-interface-probe.vvp'],capture_output=True,timeout=60)
(P/'simulation.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and b'PASS' in r.stdout,r.stdout.decode(errors='replace')
assert all(sha(Path(p))==h for p,h in hashes.items())
(P/'SIMULATION.json').write_text(json.dumps({'passed':True,'input_sha256':hashes,'pll_model':'ideal33MHz; Gowin actualIOBUF model'},indent=2)+'\n')
print(r.stdout.decode(errors='replace'))
