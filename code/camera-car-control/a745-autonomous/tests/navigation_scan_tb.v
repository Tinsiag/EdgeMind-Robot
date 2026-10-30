`timescale 1ns/1ps
module navigation_scan_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,stream_valid=1,point_valid=0;
 reg [15:0] angle=0,distance=2000;reg [7:0] confidence=100;
 wire scan_valid,left_clear,right_clear;wire [15:0] front,left,right,rear;wire [7:0] scan_sequence;
 a745_navigation_scan dut(.*);
 task point(input integer a,input integer d);
  begin @(negedge clk);angle=16'(a);distance=16'(d);point_valid=1;
   @(negedge clk);point_valid=0;repeat(5) @(negedge clk);end
 endtask
 task scan(input integer scene);
  integer i,d;
  begin
   for(i=0;i<72;i=i+1) begin
    d=2000;
    if(i==54 && scene!=0) d=500;
    if(i==0 && scene==1) d=250;
    if(i==36 && scene==2) d=250;
    point(i*500,d);
   end
   point(0,scene==1 ? 250:2000);
  end
 endtask
 initial begin
  repeat(4) @(negedge clk);rst_n=1;
  if(scan_valid || left_clear || right_clear) $fatal(1,"clear without complete scan");
  scan(0);scan(0);
  if(!scan_valid || !left_clear || !right_clear || front!=2000) $fatal(1,"clear scene failed");
  // A 50cm front obstacle permits rotation, while a close right return
  // excludes only the right swept envelope. No global-nearest lockout.
  scan(1);scan(1);
  if(!scan_valid || !left_clear || right_clear || front!=500 || right!=250)
   $fatal(1,"right obstacle did not permit only left turn");
  scan(2);scan(2);
  if(!scan_valid || left_clear || !right_clear || left!=250)
   $fatal(1,"left obstacle did not permit only right turn");
  scan(0);scan(0);
  // Current close data revokes an already published clearance immediately.
  point(18000,150);
  if(left_clear || right_clear) $fatal(1,"close body collision not immediate");
  stream_valid=0;repeat(5) @(negedge clk);
  if(scan_valid || left_clear || right_clear) $fatal(1,"stream loss not fail closed");
  stream_valid=1;confidence=0;scan(0);scan(0);
  if(scan_valid || left_clear || right_clear) $fatal(1,"low confidence scan accepted");
  confidence=100;scan(0);scan(0);
  if(!scan_valid) $fatal(1,"valid stream did not recover");
  repeat(302) begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end
  if(scan_valid || left_clear || right_clear) $fatal(1,"stale scan retained clearance");
  $display("PASS directional CAD turn envelope, 500mm front, side choice, immediate collision, scan coverage/confidence/staleness");$finish;
 end
 initial begin #1000000;$fatal(1,"navigation scan watchdog");end
endmodule
