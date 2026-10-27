`timescale 1ns/1ps
module Gowin_PLL(input clkin,mdclk,reset,output reg clkout0=0,output lock);
 always #15.151515 clkout0=~clkout0;
 assign lock=!reset;
endmodule
module official_probe_tb;
 reg clk50M=0,reset_n=0;always #10 clk50M=~clk50M;
 wire [15:0] TFT_rgb;wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm;
 wire [7:0] led;wire left_in1,left_in2,right_in1,right_in2;
 GSR GSR(.GSRI(1'b1));
 official_probe dut(.*);
 initial begin
 wait(reset_n);#500;
 #200;
 if(TFT_pwm!==0 || led[3]!==0) $fatal(1,"BL low/readback");
 @(negedge clk50M);force dut.startup_count=24'd9999998;#20;release dut.startup_count;#200;
 if(TFT_pwm!==1 || led[3]!==1) $fatal(1,"BL high/readback");
 
 #2000000;
 if(dut.edge_count<100 || !led[5]) $fatal(1,"Missing PCLK/DE pad readback count=%d de=%b",dut.edge_count,led[5]);
end
integer x=0,y=0,frames=0,pixels=0,colors[0:7],k,index;
 reg was_de=0,was_vs=0;reg [15:0] expected;
 realtime launch=0,last_sample=0;
 always @(TFT_rgb or TFT_de or TFT_hs or TFT_vs) if(reset_n && $time>200) begin
  if(TFT_clk!==0) $fatal(1,"probe changes at sample edge");launch=$realtime;
 end
 always @(posedge TFT_clk) if(reset_n) begin
  if($time>200 && launch && $realtime-launch<15.15) $fatal(1,"probe setup");
  if(TFT_vs && !was_vs) begin
   if(frames>0 && pixels!=800*480) $fatal(1,"probe incomplete frame %d",pixels);
   frames=frames+1;pixels=0;y=0;
   if(frames==3) begin
    for(k=0;k<8;k=k+1) if(colors[k]<1000) $fatal(1,"missing colour %d",k);
    if({left_in1,left_in2,right_in1,right_in2}!==0 || !TFT_pwm || !led[3] || !dut.backlight_on) $fatal(1,"probe safety/backlight");
    $display("PASS physicalIOBUF readback and backlight stays on after startup plus official800x480 eight colour blocks,2 complete frames,33MHz falling launch/rising sample,motor pads low");$finish;
   end
  end
  was_vs=TFT_vs;
  if(TFT_de) begin
   if(!was_de) x=0;
   if(x>3 && x<797 && x%400>3 && y>3 && y<477 && y%120>3) begin
    index=(y/120)*2+(x/400);
    case(index)
     0:expected=0;1:expected=16'h001f;2:expected=16'hf800;3:expected=16'hf81f;
     4:expected=16'h07e0;5:expected=16'h07ff;6:expected=16'hffe0;7:expected=16'hffff;
    endcase
    if(TFT_rgb!==expected) $fatal(1,"probe colour at %d,%d got %h expected %h",x,y,TFT_rgb,expected);
    colors[index]=colors[index]+1;
   end
   x=x+1;pixels=pixels+1;
  end else if(was_de) begin if(x!=800) $fatal(1,"probe line width %d",x);y=y+1;end
  was_de=TFT_de;
 end
 initial begin for(k=0;k<8;k=k+1) colors[k]=0;#1;reset_n=1;#2;reset_n=0;#53;reset_n=1;end
 initial begin #40000000;$fatal(1,"probe watchdog");end
endmodule
