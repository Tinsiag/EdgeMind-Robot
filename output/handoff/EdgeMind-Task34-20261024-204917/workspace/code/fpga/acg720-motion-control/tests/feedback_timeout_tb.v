`timescale 1ns/1ps
module feedback_timeout_tb;
 reg clk=0,rstn=0,sample=0,monitor=0,invalid=0;
 reg signed [1:0] step=0;
 wire signed [31:0] count,delta;wire [31:0] bad;wire timeout;
 always #5 clk=~clk;
 encoder_counter #(.TIMEOUT_MS(30)) dut(.clk(clk),.rstn(rstn),.step(step),.invalid_step(invalid),.sample_tick(sample),.monitor_enable(monitor),.count(count),.delta(delta),.invalid_count(bad),.feedback_timeout(timeout));
 task tick;begin @(negedge clk);sample=1;@(negedge clk);sample=0;end endtask
 initial begin
  repeat(4) @(negedge clk);rstn=1;
  repeat(50) tick;if(timeout) $fatal(1,"Idle timeout");
  monitor=1;tick;if(timeout) $fatal(1,"Immediate first-motion fault");
  tick;if(timeout) $fatal(1,"Early timeout");tick;if(!timeout) $fatal(1,"Missing timeout");
  @(negedge clk);step=1;@(negedge clk);step=0;if(timeout) $fatal(1,"Edge did not renew window");
  tick;tick;if(timeout) $fatal(1,"Feedback window too short");
  monitor=0;tick;if(timeout) $fatal(1,"Disabled monitoring not cleared");
  // Count sampling must not be skipped when a step coincides with sample_tick.
  @(negedge clk);step=1;@(negedge clk);step=0;
  @(negedge clk);step=1;sample=1;@(negedge clk);step=0;sample=0;
  if(delta!=1) $fatal(1,"Sample/edge collision skipped delta=%0d",delta);
  $display("PASS feedback idle, first motion, timeout, edge renewal, sample collision");$finish;
 end
endmodule
