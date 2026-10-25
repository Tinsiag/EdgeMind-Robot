`timescale 1ns/1ps
module pi_signed_tb;
 reg clk=0,rstn=0,enable=0,update=0;
 reg signed [31:0] target=0,measured=0;
 reg [15:0] limit=100,ramp=10;
 wire signed [31:0] command,applied;
 always #5 clk=~clk;
 wheel_pi_controller dut(.clk(clk),.rstn(rstn),.enable(enable),.update(update),.target_speed(target),.measured_speed(measured),.output_limit(limit),.ramp_limit(ramp),.command(command),.applied_target(applied));
 task tick;begin @(negedge clk);update=1;@(negedge clk);update=0;repeat(12) @(negedge clk);end endtask
 task reset_pi;begin @(negedge clk);enable=0;tick;enable=1;end endtask
 initial begin
  repeat(4) @(negedge clk);rstn=1;enable=1;target=-50;
  tick;if(applied!=-10 || command>=0) $fatal(1,"Negative ramp/sign");
  repeat(8) tick;if(applied!=-50||command < -100 || command>=0) $fatal(1,"Negative target");
  target=50;tick;if(applied!=-40) $fatal(1,"Sign crossing ramp");
  repeat(12) tick;if(applied!=50||command<=0||command>100) $fatal(1,"Positive target");
  target=0;@(negedge clk);if(command!=0||applied!=0) $fatal(1,"Zero target did not stop");
  reset_pi;target=-32'sd2147483647;ramp=65535;limit=65535;tick;
  if(applied!=-32767 || command!=-1024) $fatal(1,"Negative overflow/full-scale clamp %0d %0d",applied,command);
  reset_pi;target=32'sd2147483647;tick;
  if(applied!=32767||command!=1024) $fatal(1,"Positive overflow clamp");
  enable=0;tick;if(command!=0) $fatal(1,"Disable");
  $display("PASS PI signed ramps, sign crossing, saturation, overflow, zero/disable");$finish;
 end
endmodule
