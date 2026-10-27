"""Isolated official chapter28 colour blocks; never programs hardware."""
from pathlib import Path
import shutil,subprocess,hashlib,json,time
OUT=Path(__file__).resolve().parent/'official-probe-v3'
ROOT=Path(__file__).resolve().parents[2]
SOURCE=OUT.parent/'official-ch28'
OUT.mkdir(exist_ok=True)
for src in (SOURCE/'src').rglob('*'):
 if src.is_file():
  dst=OUT/'src'/src.relative_to(SOURCE/'src');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
top=OUT/'src/tft_ctrl_test.v'
text=top.read_text(encoding='utf-8')
assert text.count('assign tft_reset_p = ~pll_locked;')==1
text=text.replace('assign tft_reset_p = ~pll_locked;', '''reg [1:0] tft_ready;
    always @(posedge clk_ctrl or negedge pll_locked)
      if(!pll_locked) tft_ready<=0;else tft_ready<={tft_ready[0],1'b1};
    assign tft_reset_p = ~tft_ready[1];''')
top.write_text(text,encoding='utf-8')
wrapper='''`timescale 1ns/1ps
module official_probe(input wire clk50M,reset_n,output wire [15:0] TFT_rgb,
 output wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm,output wire [7:0] led,
 output wire left_in1,left_in2,right_in1,right_in2);
 wire [15:0] rgb;wire hs,vs,de,pwm,pclk;
 tft_ctrl_test official(.clk50M(clk50M),.reset_n(reset_n),.TFT_rgb(rgb),
  .TFT_hs(hs),.TFT_vs(vs),.TFT_clk(pclk),.TFT_de(de),.TFT_pwm(pwm));
 // Preserve all official RTL. Retiming outputs on the falling edge centers
 // stable data on the documented WKS43189 rising-edge sample; no ODDR path.
 (* syn_preserve=1, syn_keep=1 *) reg [18:0] pins=0;
 always @(negedge pclk) pins<={de,hs,vs,rgb};
 assign {TFT_de,TFT_hs,TFT_vs,TFT_rgb}=pins;
 assign TFT_clk=pclk;assign TFT_pwm=pwm;
 reg [25:0] sys_count=0;reg [4:0] frames=0;reg old_vs=0;
 always @(posedge clk50M or negedge reset_n) if(!reset_n) sys_count<=0;else sys_count<=sys_count+1'b1;
 always @(posedge pclk or negedge reset_n) if(!reset_n) begin frames<=0;old_vs<=0;end
 else begin old_vs<=vs;if(vs && !old_vs) frames<=frames+1'b1;end
 assign led={5'b00000,frames[4],sys_count[24],1'b1};
 assign left_in1=1'b0;assign left_in2=1'b0;assign right_in1=1'b0;assign right_in2=1'b0;
endmodule
'''
(OUT/'wrapper.v').write_text(wrapper)
cst=(SOURCE/'src/tft_ctrl.cst').read_text(encoding='utf-8-sig')
base=(ROOT/'code/camera-car-control/a741-fpga-fusion/.local/platform-basic-tft800-screen-test-diagnostic/a741.cst').read_text()
import re
cst+='\n'+'\n'.join(line for line in base.splitlines() if re.match(r'IO_(LOC|PORT) "(led\[|left_in|right_in)',line))+'\n'
(OUT/'probe.cst').write_text(cst,encoding='utf-8')
(OUT/'probe.sdc').write_text('''create_clock -name sys_clk -period20 [get_ports {clk50M}]
create_generated_clock -name lcd33m -source [get_ports {clk50M}] -multiply_by33 -divide_by50 [get_pins {official/Gowin_PLL/u_pll/PLLA_inst/CLKOUT0}]
set_max_delay10 -to [get_ports {TFT_rgb[*] TFT_hs TFT_vs TFT_de TFT_pwm}]
set_false_path -to [get_pins {official/tft_ready_*/CLEAR}]
'''.replace('-period20','-period 20').replace('-multiply_by33','-multiply_by 33').replace('-divide_by50','-divide_by 50').replace('set_max_delay10','set_max_delay 10'))
files=['src/disp_driver.v','src/disp_parameter_cfg.v','src/gowin_pll/gowin_pll.v','src/gowin_pll/gowin_pll_mod.v','src/pll_init.v','src/tft_ctrl_test.v','wrapper.v']
project='''<?xml version="1.0" encoding="UTF-8"?><Project><Template>FPGA</Template><Version>5</Version><Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device><FileList>'''
project+=''.join(f'<File path="{f}" type="file.verilog" enable="1"/>' for f in files)
project+='<File path="probe.cst" type="file.cst" enable="1"/><File path="probe.sdc" type="file.sdc" enable="1"/></FileList></Project>'
(OUT/'probe.gprj').write_text(project)
(OUT/'build.tcl').write_text('''cd [file dirname [file normalize [info script]]]
open_project probe.gprj
set_option -top_module official_probe
set_option -output_base_name probe
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_cpu_as_gpio 1
set_option -bit_security 0
set_option -user_code 0000A728
set_option -route_option 1
set_option -place_option 1
set_option -timing_driven 1
set_option -correct_hold_violation 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
''')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={f:sha(OUT/f) for f in files+['probe.cst','probe.sdc','build.tcl','probe.gprj']}
started=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
changed=any(sha(OUT/f)!=h for f,h in hashes.items())
artifact=OUT/'impl/pnr/probe.fs'
result={'returncode':r.returncode,'seconds':time.time()-started,'source_sha256':hashes,'sources_changed':changed,
 'artifact_sha256':sha(artifact) if artifact.is_file() else None,'hardware_programmed':False,'timing_signed_off':False,
 'official_scanner_pll_colors_unchanged':True,'top_reset_change':'synchronize PLL lock release into scan clock; scoped reset synchronizer assertion exception',
 'adapter':'falling-edge output retime for rising-edge panel; motor pads GND; heartbeat LEDs',
 'note':'isolated diagnostic only; main camera/DDR/OSD project preserved'}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert r.returncode==0 and not changed and artifact.is_file()
