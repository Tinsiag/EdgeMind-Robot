`timescale 1ns/1ps
module rotate_cancel_tb;
 reg clk=0,rstn=0,start=0,cancel=0;
 reg signed [31:0] angle=-1000,lc=0,rc=0;
 reg [31:0] speed=50;
 wire active,done;wire signed [31:0] lt,rt;
 always #5 clk=~clk;
 rotate_controller dut(.clk(clk),.rstn(rstn),.start(start),.cancel(cancel),.angle_mdeg(angle),.max_speed(speed),.left_count(lc),.right_count(rc),.left_speed(32'sd0),.right_speed(32'sd0),.counts_per_degree_q16(32'd65536),.tolerance_counts(32'd4),.active(active),.done(done),.left_target(lt),.right_target(rt));
 task launch;begin @(negedge clk);start=1;@(negedge clk);start=0;repeat(2) @(negedge clk);end endtask
 initial begin
  repeat(4) @(negedge clk);rstn=1;launch;
  if(dut.target_delta!=-1000||lt<=0||rt>=0) $fatal(1,"Negative angle sign");
  speed=1000;repeat(3) @(negedge clk);
  if(lt!=50||rt!=-50) $fatal(1,"Speed not latched");
  lc=1000;rc=-1000;@(negedge clk);
  if(active||!done||lt!=0||rt!=0) $fatal(1,"Completion failed");
  repeat(3) @(negedge clk);if(active) $fatal(1,"Completion restarted");
  angle=1000;speed=50;launch;
  if(lt>=0||rt<=0) $fatal(1,"Positive angle sign");
  cancel=1;start=1;@(negedge clk);
  if(active||done||lt!=0||rt!=0) $fatal(1,"Cancel priority");
  start=0;cancel=0;repeat(3) @(negedge clk);
  if(active) $fatal(1,"Cancelled motion restarted");
  $display("PASS rotate signed angle, latched speed, completion, cancel priority/no restart");$finish;
 end
endmodule
