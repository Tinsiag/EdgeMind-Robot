`timescale 1ns/1ps
module Gowin_PLL(input clkin,mdclk,reset,output reg clkout0=0,output lock);
 always #55.555556 clkout0=~clkout0;
 assign lock=!reset;
endmodule
module control_mapping_tb;
 reg clk50M=0,reset_n=0;always #10 clk50M=~clk50M;
 wire [15:0] TFT_rgb;wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm;
 wire [7:0] led;wire left_in1,left_in2,right_in1,right_in2;
 GSR GSR(.GSRI(1'b1));
 // Accelerate only the number of frames per mode. Pixel/line/frame timing
 // and all I/O primitives are identical to the hardware candidate.
 official_probe #(.MODE_FRAMES(3)) dut(.*);
 integer totals[0:2],colors[0:7],mode_old=0,x=0,y=0,k,index,transitions=0;
 reg was_de=0,was_vs=0;wire raster_de=dut.mode==1 ? TFT_pwm:TFT_de;
 reg [15:0] expected;realtime changed=0;
 always @(TFT_rgb or TFT_de or TFT_pwm or TFT_hs or TFT_vs) if(reset_n && $time>200) begin
  if(TFT_clk!==1) $fatal(1,"output changes at sampling edge");
  changed=$realtime;
 end
 always @(negedge TFT_clk) if(reset_n && $time>500) begin
  if(changed && $realtime-changed<55.55) $fatal(1,"half period setup missing");
  if(led[7:6]!==dut.mode) $fatal(1,"mode LED mismatch");
  case(dut.mode)
   0:if(TFT_pwm!==1 || TFT_de!==dut.pins[18]) $fatal(1,"normal mapping");
   1:if(TFT_de!==1 || TFT_pwm!==dut.pins[18]) $fatal(1,"swapped mapping");
   2:if(TFT_de!==dut.pins[18] || TFT_pwm!==dut.pins[18]) $fatal(1,"common DE mapping");
  endcase
  if(dut.mode!=mode_old) begin transitions=transitions+1;mode_old=dut.mode;end
  if(TFT_vs && !was_vs) begin
   y=0;
   if(transitions>=3) begin
    for(k=0;k<3;k=k+1) if(totals[k]<480*272*2) $fatal(1,"not two complete frames mode %0d",k);
    for(k=0;k<8;k=k+1) if(colors[k]<1000) $fatal(1,"missing colour %0d",k);
    if(dut.edge_count<100 || !led[5] || {left_in1,left_in2,right_in1,right_in2}!==0) $fatal(1,"PAD activity/motor lock");
    $display("PASS three mapping modes, unchanged 480x272/9MHz raster, all eight colours, physical IOBUF readback, full mode cycle, falling-edge half-cycle output timing, motors low");
    $finish;
   end
  end
  was_vs=TFT_vs;
  if(raster_de) begin
   if(!was_de) x=0;
   if(x>3 && x<477 && x%240>3 && y>3 && y<269 && y%68>3) begin
    index=(y/68)*2+(x/240);
    case(index)
     0:expected=0;1:expected=16'h001f;2:expected=16'hf800;3:expected=16'hf81f;
     4:expected=16'h07e0;5:expected=16'h07ff;6:expected=16'hffe0;7:expected=16'hffff;
    endcase
    if(TFT_rgb!==expected) $fatal(1,"mode %0d pixel %0d,%0d",dut.mode,x,y);
    colors[index]=colors[index]+1;
   end
   totals[dut.mode]=totals[dut.mode]+1;
   x=x+1;
  end else if(was_de) begin
   if(x!=480) $fatal(1,"bad active line %0d",x);
   y=y+1;
  end
  was_de=raster_de;
 end
 initial begin
  for(k=0;k<3;k=k+1) totals[k]=0;
  for(k=0;k<8;k=k+1) colors[k]=0;
  #1;reset_n=1;#2;reset_n=0;#53;reset_n=1;
 end
 initial begin #250000000;$fatal(1,"watchdog");end
endmodule
