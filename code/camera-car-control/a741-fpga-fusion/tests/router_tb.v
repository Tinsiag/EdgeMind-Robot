`timescale 1ns/1ps
module router_tb;
 reg clk=0;always #5 clk=~clk;reg rst_n=0;
 reg cv=0,cl=0,tv=0,tl=0;wire cr,tr;
 a741_router dut(.clk(clk),.rst_n(rst_n),.eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),
  .eth_tx_ready(1'b0),.control_rx_ready(1'b1),.control_tx_data(8'haa),.control_tx_valid(cv),.control_tx_last(cl),
  .control_tx_length(16'd7),.control_tx_ready(cr),.telemetry_data(8'hbb),.telemetry_valid(tv),.telemetry_last(tl),
  .telemetry_length(16'd3),.telemetry_ready(tr));
 initial begin
  #30;rst_n=1;force dut.uhr=1;force dut.upr=0;
  @(negedge clk);tv=1;repeat(3) @(negedge clk);cv=1;
  repeat(10) begin @(negedge clk);if(dut.tx_control || dut.tx_length!=3 || dut.upd!=8'hbb || tr || cr) $fatal(1,"debug packet lock/backpressure");end
  force dut.upr=1;tl=1;@(negedge clk);tl=0;tv=0;repeat(4) @(negedge clk);
  if(!dut.tx_control || dut.tx_length!=7 || dut.upd!=8'haa) $fatal(1,"control did not follow telemetry");
  cl=1;@(negedge clk);cl=0;cv=0;
  $display("PASS debug-only Ethernet control/telemetry packet lock and backpressure");$finish;
 end
 initial begin #2000;$fatal(1,"router watchdog");end
endmodule
