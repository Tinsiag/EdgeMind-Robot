`timescale 1ns/1ps
module mode_display_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0;reg [1:0] mode=1;wire dio,rclk,sclk;
 reg [15:0] shifted=0;integer bits=0,frames=0;
 a745_mode_display #(.DIV(2)) dut(.*);
 always @(posedge sclk)begin shifted={shifted[14:0],dio};bits=bits+1;end
 always @(posedge rclk)begin
  if(bits!=16)$fatal(1,"wrong shift length");
  if(frames>0 && shifted!=(mode==1 ? 16'hf901:mode==2 ? 16'ha401:16'hb001))$fatal(1,"wrong segment/digit/order %h",shifted);
  bits=0;frames=frames+1;
 end
 initial begin
  repeat(4)@(negedge clk);rst_n=1;repeat(160)@(negedge clk);
  rst_n=0;mode=2;frames=0;bits=0;repeat(4)@(negedge clk);rst_n=1;repeat(160)@(negedge clk);
  if(frames<2)$fatal(1,"no scan refresh");
  $display("PASS reference 74HC595 16bit MSB order, active-low segments, one digit and latch timing");$finish;
 end
endmodule
