`timescale 1ns/1ps
// A checksum-valid actual end1 Linux datagram, including DF and nonzero ID/DSCP.
module detection_linux_tb;
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,valid=0,last=0,user=0;reg [7:0] data=0;
 wire ready,update;wire [771:0] detections;wire [7:0] accepted;
 a745_detection_rx dut(.*,.update_ready(1'b1));
 reg [7:0] p[0:81];integer i;
 initial begin
  $readmemh("tests/detection_linux_frame.hex",p);
  repeat(4)@(negedge clk);rst_n=1;
  for(i=0;i<82;i=i+1)begin
   @(negedge clk);valid=1;data=p[i];last=i==81;
   if(i%7==0)begin @(negedge clk);valid=0;end
  end
  @(negedge clk);valid=0;last=0;repeat(12)@(negedge clk);
  if(accepted!=1 || detections[3:0]!=p[50] || detections[4+:16]!={p[59],p[58]})
   $fatal(1,"captured Linux frame rejected count=%d",accepted);
  $display("PASS real Linux ED10 frame checksum/header/box decode with AXI stalls");$finish;
 end
endmodule
