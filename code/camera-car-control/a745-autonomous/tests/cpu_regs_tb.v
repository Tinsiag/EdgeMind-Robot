`timescale 1ns/1ps
module cpu_regs_tb;
 reg clk=0;always #5 clk=~clk;
 reg wen=0;reg [5:0] waddr=0,raddr1=0,raddr2=0;reg [31:0] wdata=0;
 wire [31:0] rdata1,rdata2;integer i;
 a745_cpu_regs dut(.*);
 function [31:0] value(input integer index);value=32'h93c50000 ^ (index*32'h01020409);endfunction
 initial begin
  for(i=1;i<32;i=i+1) begin
   @(negedge clk);wen=1;waddr=i;wdata=value(i);
  end
  @(negedge clk);wen=0;
  for(i=1;i<32;i=i+1) begin
   // Addresses change away from a clock edge; read ports must update now.
   #1;raddr1=i;raddr2=32-i;#1;
   if(rdata1!==value(i) || rdata2!==value(32-i)) $fatal(1,"asynchronous register reads %d",i);
   @(negedge clk);
  end
  wen=1;waddr=0;wdata=32'hffffffff;@(negedge clk);wen=0;raddr1=0;raddr2=32;#1;
  if(rdata1!==0 || rdata2!==0) $fatal(1,"x0 or unsupported high bank");
  $display("PASS RV32 FF register file: all31 writable registers, dual combinational reads, x0 and high-bank isolation");$finish;
 end
endmodule
