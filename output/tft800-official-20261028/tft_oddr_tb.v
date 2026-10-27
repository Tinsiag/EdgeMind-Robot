`timescale 1ns/1ps
module tft_oddr_tb;
 reg clk=0;always #15.151515 clk=~clk;
 wire pclk;
 GSR GSR(.GSRI(1'b1));
 ODDR dut(.CLK(clk),.D0(1'b0),.D1(1'b1),.TX(1'b1),.Q0(pclk),.Q1());
 integer edges=0;
 always @(clk) begin
  #0.01;
  if($time>200) begin
   if(pclk!==~clk) $fatal(1,"Gowin ODDR not producing inverted pixel clock");
   edges=edges+1;
  end
 end
 initial begin #2000;if(edges<100) $fatal(1,"missing ODDR edges");
  $display("PASS Gowin GW5A ODDR primitive: D0=0 D1=1 yields opposite-phase sample clock");$finish;end
endmodule
