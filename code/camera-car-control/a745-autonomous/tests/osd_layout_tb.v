`timescale 1ns/1ps
module osd_layout_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,frame_blank=0,de=1,status_update=0,pixel_valid=1;
 reg [10:0] x=400,y=200;reg [15:0] pixel=16'h1234;
 reg [895:0] status_snapshot=0;reg [255:0] fusion_snapshot=0;wire [15:0] rgb;
 a745_osd #(.PIPELINED(1)) dut(.*);
 task publish;
  begin
   @(negedge clk);status_update=1;@(negedge clk);status_update=0;
   wait(dut.state==5);@(negedge clk);frame_blank=1;@(negedge clk);frame_blank=0;
   repeat(8) @(negedge clk);
  end
 endtask
 initial begin
  status_snapshot[175:160]=16'h230b;status_snapshot[479:464]=1200;
  status_snapshot[495:480]=650;status_snapshot[511:496]=800;
  status_snapshot[575:544]=32'h300a5656;status_snapshot[799:792]=(11<<3)|1;
  fusion_snapshot[64]=1;fusion_snapshot[47:32]=-16384;fusion_snapshot[63:48]=8192;
  #30;rst_n=1;publish();
  if(dut.lines[1][255-2*8-:48]!="-090.0" || dut.lines[1][255-11*8-:48]!=" 045.0") $fatal(1,"signed attitude layout");
  if(dut.lines[2][255-2*8-:48]!=" 01200" || dut.lines[3][255-5*8-:48]!="IDLE  ") $fatal(1,"range/state layout");
  if(dut.lines[0][255-22*8-:48]!="CAM:OK") $fatal(1,"camera ready label");
  if(dut.cell_position(0)!==0 || dut.cell_position(382)>>3!=31) $fatal(1,"full-width character coverage");
  if(rgb!==pixel || dut.health_fault || dut.health_wait) $fatal(1,"center video or healthy color");
  x=16;y=12;repeat(6) @(negedge clk);
  if(rgb!==16'h1b4c) $fatal(1,"inset border color");
  status_snapshot[207:192]=16'h0004;status_snapshot[183:176]=8;publish();
  if(!dut.health_fault || dut.lines[3][255-5*8-:48]!="FAULT " || dut.lines[3][255-25*8-:32]!="0004") $fatal(1,"fault text/color");
  if(rgb!==16'hf980) $fatal(1,"fault border");
  status_snapshot[791:784]=4;publish();
  if(dut.lines[3][255-7*8-:64]!="REG:300A" || dut.lines[3][255-16*8-:56]!="READ:56") $fatal(1,"camera diagnostic layout");
  if(dut.VIEW_WIDTH!=480 || dut.VIEW_HEIGHT!=272) $fatal(1,"physical visible area");
  $display("PASS HUD signed values, 32 columns inside480x272, diagnostics, inset border, live video and frame-coherent fault state");$finish;
 end
 initial begin #100000;$fatal(1,"HUD watchdog");end
endmodule
