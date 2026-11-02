`timescale 1ns/1ps
module detection_hud_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,frame_blank=0,update=0;reg [771:0] detections=0;
 reg [10:0] x=90,y=12;reg [15:0] pixel=16'h1234;
 wire [15:0] box_rgb,rgb;reg [895:0] status_snapshot=0;
 a745_detection_overlay boxes(.*,.rgb(box_rgb),.present());
 a745_osd #(.PIPELINED(1)) hud(.clk(clk),.rst_n(rst_n),.frame_blank(frame_blank),.de(1'b1),
  .x(x),.y(y),.pixel(box_rgb),.pixel_valid(1'b1),.status_snapshot(status_snapshot),
  .status_update(update),.fusion_snapshot(256'd0),.rgb(rgb));
 initial begin
  status_snapshot[175:160]=16'h230b;status_snapshot[799:792]=(11<<3)|1;
  repeat(3)@(negedge clk);rst_n=1;
  detections[3:0]=1;detections[4+:16]=10;detections[20+:16]=12;
  detections[36+:16]=100;detections[52+:16]=200;update=1;
  @(negedge clk);update=0;wait(hud.state==5);
  @(negedge clk);frame_blank=1;@(negedge clk);frame_blank=0;
  repeat(6)@(negedge clk);
  if(box_rgb!==16'h07e0 || rgb!==16'h1b4c)$fatal(1,"HUD must cover box at border %h",rgb);
  y=100;repeat(6)@(negedge clk);if(rgb!==16'h07e0)$fatal(1,"box outside HUD");
  x=100;repeat(6)@(negedge clk);if(rgb!==pixel)$fatal(1,"camera interior changed");
  $display("PASS detection below HUD, existing two-cycle RGB pipeline, original pixel interior");$finish;
 end
 initial begin #50000;$fatal(1,"timeout");end
endmodule
