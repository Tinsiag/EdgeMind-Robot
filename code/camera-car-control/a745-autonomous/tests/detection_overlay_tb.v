`timescale 1ns/1ps
module detection_overlay_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,frame_blank=0,update=0;reg [771:0] detections=0;
 reg [10:0] x=90,y=20;reg [15:0] pixel=16'h1234;wire [15:0] rgb;wire present;
 a745_detection_overlay #(.TTL_FRAMES(2)) dut(.*);
 task frame;
 begin @(negedge clk);frame_blank=1;repeat(3)@(negedge clk);frame_blank=0;@(negedge clk);end endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  detections[3:0]=1;detections[4+:16]=10;detections[20+:16]=20;
  detections[36+:16]=100;detections[52+:16]=200;update=1;
  @(negedge clk);update=0;#1;if(rgb!=pixel || present)$fatal(1,"early commit");
  frame;#1;if(rgb!=16'h07e0 || !present)$fatal(1,"coordinate x+80");
  x=93;y=23;#1;if(rgb!=pixel)$fatal(1,"interior overwritten");
  x=180;#1;if(rgb!=16'h07e0)$fatal(1,"right edge");
  frame;frame;frame;#1;if(present || rgb!=pixel)$fatal(1,"stale boxes");
  $display("PASS detection overlay frame atomicity crop mapping interior and TTL");$finish;
 end
endmodule
