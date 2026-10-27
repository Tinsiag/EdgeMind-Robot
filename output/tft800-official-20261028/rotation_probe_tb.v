`timescale 1ns/1ps
module Gowin_PLL(input clkin,mdclk,reset,output reg clkout0=0,output lock);
 always #15.151515 clkout0=~clkout0;
 assign lock=!reset;
endmodule
module rotation_probe_tb;
 reg clk50M=0,reset_n=0;always #10 clk50M=~clk50M;
 wire [15:0] TFT_rgb;wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm;
 wire [7:0] led;wire left_in1,left_in2,right_in1,right_in2;
 GSR GSR(.GSRI(1'b1));
 official_probe #(.MODE_FRAMES(3)) dut(.*);
 integer x=0,y=0,pixels=0,lines=0,tick=0,line_start=0,last_line_start=0;
 integer frame_mode=0,completed[0:1],palette_count[0:7],k,src_x,src_y,index;
 integer low_hs=0,hs_mode=0,last_vstart=0,vstart_mode=0;
 integer width,height;
 reg was_de=0,was_vs=0,was_hs=0,have_frame=0,count_hs=0;
 reg [15:0] palette[0:7];
 realtime launch=0;
 always @(TFT_rgb or TFT_de or TFT_hs or TFT_vs) if(reset_n && $time>200) begin
  if(TFT_clk!==0) $fatal(1,"launch at wrong clock edge");
  launch=$realtime;
 end
 always @(posedge TFT_clk) if(reset_n && $time>500) begin
  tick=tick+1;
  if(launch && $realtime-launch<15.15) $fatal(1,"missing setup interval");
  if(TFT_pwm!==1 || led[7]!==0 || led[6]!==dut.portrait) $fatal(1,"backlight/mode indicator");
  if(TFT_vs && !was_vs) begin
   if(have_frame) begin
    if(pixels!=384000 || lines!=(frame_mode ? 800:480)) $fatal(1,"incomplete mode%0d frame pixels=%0d lines=%0d",frame_mode,pixels,lines);
    for(k=0;k<8;k=k+1) if(palette_count[k]!=48000) $fatal(1,"unequal rotated block %0d %0d",k,palette_count[k]);
    completed[frame_mode]=completed[frame_mode]+1;
    if(completed[0]>=2 && completed[1]>=2) begin
     if(dut.edge_count<100 || !led[5] || !led[3] || {left_in1,left_in2,right_in1,right_in2}!==0) $fatal(1,"PAD activity/motor lock");
     $display("PASS clockwise90 inverse coordinate mapping for all pixels in two full800x480 frames and two full480x800 frames; raster1056x525/525x1056,33MHz,constant BL,actual IOBUF readback,motors low");
     $finish;
    end
   end
   frame_mode=dut.portrait;have_frame=1;pixels=0;lines=0;x=0;y=0;last_line_start=0;
   for(k=0;k<8;k=k+1) palette_count[k]=0;
  end
  if(!TFT_vs && was_vs) begin
   if(last_vstart && vstart_mode==dut.portrait && tick-last_vstart!=554400) $fatal(1,"wrong frame period %0d",tick-last_vstart);
   last_vstart=tick;vstart_mode=dut.portrait;
  end
  if(!TFT_hs && was_hs) begin low_hs=0;hs_mode=dut.portrait;count_hs=1;end
  if(!TFT_hs) low_hs=low_hs+1;
  if(TFT_hs && !was_hs && count_hs) begin
   if(hs_mode==dut.portrait && low_hs!=(hs_mode ? 2:128)) $fatal(1,"wrong HS pulse %0d",low_hs);
   count_hs=0;
  end
  width=frame_mode ? 480:800;height=frame_mode ? 800:480;
  if(TFT_de && have_frame) begin
   if(!was_de) begin
    x=0;line_start=tick;
    if(last_line_start && tick-last_line_start!=(frame_mode ? 525:1056)) $fatal(1,"wrong line period");
    last_line_start=tick;
   end
   // Independent inverse clockwise transform of the ORIGINAL800x480 image.
   // Landscape mode rescales the rotated480x800 image into800x480.
   src_x=(y*800)/height;
   src_y=479-(x*480)/width;
   index=(src_y/120)*2+(src_x/400);
   if(x>=width || y>=height || TFT_rgb!==palette[index]) $fatal(1,"rotation mode%0d pixel %0d,%0d got%h expected%h",frame_mode,x,y,TFT_rgb,palette[index]);
   pixels=pixels+1;palette_count[index]=palette_count[index]+1;x=x+1;
  end else if(was_de && have_frame) begin
   if(x!=width) $fatal(1,"wrong active width %0d",x);
   y=y+1;lines=lines+1;
  end
  was_de=TFT_de;was_vs=TFT_vs;was_hs=TFT_hs;
 end
 initial begin
  completed[0]=0;completed[1]=0;
  palette[0]=0;palette[1]=16'h001f;palette[2]=16'hf800;palette[3]=16'hf81f;
  palette[4]=16'h07e0;palette[5]=16'h07ff;palette[6]=16'hffe0;palette[7]=16'hffff;
  for(k=0;k<8;k=k+1) palette_count[k]=0;
  #1;reset_n=1;#2;reset_n=0;#53;reset_n=1;
 end
 initial begin #160000000;$fatal(1,"watchdog");end
endmodule
