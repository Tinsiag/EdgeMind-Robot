`timescale 1ns/1ps
module path_guard_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,stream_valid=1,scan_valid=1,point_valid=0;reg [15:0] angle=0,distance=2000;reg [7:0] confidence=100;
 wire advance_clear,reverse_clear,left_exit_clear,right_exit_clear,spin_clear;
 a745_path_guard dut(.*);
 task point(input integer a,input integer d);begin
  @(negedge clk);angle=a;distance=d;point_valid=1;
  @(negedge clk);point_valid=0;repeat(5)@(negedge clk);
 end endtask
 task sweep(input integer radius);integer i;begin
  for(i=0;i<72;i=i+1)point(i*500,radius);point(0,radius);
 end endtask
 initial begin
  repeat(4)@(negedge clk);rst_n=1;
  if(advance_clear || spin_clear)$fatal(1,"startup clear");
  sweep(2000);sweep(2000);
  if(!advance_clear || !reverse_clear || !spin_clear || !left_exit_clear || !right_exit_clear)$fatal(1,"open sweep");
  // Side walls at 50cm do not obstruct the straight body corridor.
  point(0,500);point(18000,500);
  if(!advance_clear)$fatal(1,"side walls rejected straight");
  point(27000,250);if(advance_clear)$fatal(1,"front body corridor not immediate");
  sweep(2000);sweep(2000);scan_valid=0;#1;
  if(advance_clear || spin_clear)$fatal(1,"stale scan passed");
  scan_valid=1;stream_valid=0;repeat(4)@(negedge clk);
  if(advance_clear || reverse_clear)$fatal(1,"stream loss");
  $display("PASS CAD path complete scan, 50cm sides, immediate close point and stale-data gating");$finish;
 end
endmodule
