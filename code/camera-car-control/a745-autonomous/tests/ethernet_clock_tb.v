`timescale 1ns/1ps
module ethernet_clock_tb;
 GSR GSR(.GSRI(1'b1));
 reg hclk=0,reset_n=0;
 always #2 hclk=~hclk;
 wire clock125;
 CLKDIV #(.DIV_MODE("2")) dut(.HCLKIN(hclk),.RESETN(reset_n),
    .CALIB(1'b0),.CLKOUT(clock125));
 realtime previous;
 initial begin
  #1;reset_n=0;#12;reset_n=1;
  repeat(8) @(posedge clock125);
  previous=$realtime;
  repeat(100) begin
   @(clock125);
   if($realtime-previous!=4.0)$fatal(1,"125MHz clock duty/period");
   previous=$realtime;
  end
  #1;reset_n=0;#1;
  if(clock125!==0)$fatal(1,"Clock not held low during reset");
  #15;reset_n=1;repeat(8) @(posedge clock125);
  previous=$realtime;@(posedge clock125);
  if($realtime-previous!=8.0)$fatal(1,"Clock restart period");
  $display("PASS vendor dedicated CLKDIV: 125MHz, 4ns high/low and reset/restart");
  $finish;
 end
 initial begin #10000;$fatal(1,"Clock timeout");end
endmodule
