`timescale 1ns/1ps
module avoidance_escape_tb;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,command=0; reg [7:0] kind=0; reg [255:0] payload=0;
 reg lidar_valid=1; reg [15:0] front=1500,left=1500,right=1500;
 wire reply_done; wire [255:0] reply; wire en,stop,sensor_stop; wire signed [31:0] dl,dr; wire [9:0] lim;
 a741_avoidance #(.GEOMETRY_VERIFIED(1),.BUTTON_AUTONOMOUS(1)) dut(
  .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(0),.armed(1),.link_alive(1),.motor_faults(0),.imu_valid(1),.tilt_valid(1),
  .manual_left(0),.manual_right(0),.yaw(0),.roll(0),.pitch(0),.lidar_valid(lidar_valid),.lidar_front(front),.lidar_left(left),.lidar_right(right),
  .manual_stop(0),.manual_scan_valid(1),.manual_limit(400),.supervisor_alive(1),.supervisor_fault(0),.supervisor_uptime(0),
  .command(command),.kind(kind),.payload(payload),.button_start(0),.reply_done(reply_done),.reply(reply),.drive_enabled(en),.force_stop(stop),.drive_left(dl),.drive_right(dr),
  .sensor_stop(sensor_stop),.sensor_limit(lim),.state(),.fault(),.front_distance());
 task start; begin @(negedge clk);kind=8'h59;payload=1;command=1;@(negedge clk);command=0;end endtask
 task millisecond; begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end endtask
 integer i;
 initial begin
  #20;rst_n=1;start;front=300;left=400;right=400;#1;
  if(!sensor_stop || dl!==0 || dr!==0) $fatal(1,"closed corridor did not initially stop stop=%0d sensor=%0d en=%0d dl=%0d dr=%0d blocked=%0d run=%0d",stop,sensor_stop,en,dl,dr,dut.blocked,dut.avoid_running);
  for(i=0;i<205;i=i+1) millisecond;
  if(!dut.escape_reverse || dl!==-60 || dr!==-60) $fatal(1,"bounded reverse escape missing");
  left=800; millisecond;
  if(!dut.avoid_turning || dut.escape_reverse || dl!==-80 || dr!==80) $fatal(1,"side search did not turn");
  front=800; millisecond;
  if(dut.avoid_turning || dl!==60 || dr!==60) $fatal(1,"escape did not resume cruise");
  $display("PASS bounded reverse and side-search escape");$finish;
 end
 initial begin #100000;$fatal(1,"escape watchdog");end
endmodule
