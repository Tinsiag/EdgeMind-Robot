`timescale 1ns/1ps
module display_cdc_tb;
 reg sys_clk=0,disp_clk=0,reset_n=0;
 always #10 sys_clk=~sys_clk;
 always #15.151515 disp_clk=~disp_clk;
 wire sys_rst_n,disp_rst_n;
 reset_sync sr(.clk(sys_clk),.async_n(reset_n),.rst_n(sys_rst_n));
 reset_sync dr(.clk(disp_clk),.async_n(reset_n),.rst_n(disp_rst_n));
 reg [31:0] version=0,frame=0;
 always @(posedge sys_clk) if(!sys_rst_n) version<=0;else version<=version+1;
 always @(posedge disp_clk) if(!disp_rst_n) frame<=0;else frame<=frame+1;
 wire [895:0] display_snapshot;wire [255:0] display_fusion;
 wire [5:0] display_flags;wire display_update;wire [35:0] system_display_status;
 a741_display_cdc dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.disp_clk(disp_clk),.disp_rst_n(disp_rst_n),
  .status_snapshot({28{version}}),.fusion_snapshot({8{~version}}),.system_flags(version[5:0]),
  .display_status({frame[3:0],frame}),.*);
 integer snapshots=0,returns=0;
 reg [31:0] received;
 always @(posedge disp_clk) if(disp_rst_n && display_update) begin
  received=display_snapshot[31:0];
  if(display_snapshot!=={28{received}} || display_fusion!=={8{~received}} || display_flags!==received[5:0])
   $fatal(1,"Torn display status across50/33MHz");
  snapshots=snapshots+1;
 end
 always @(posedge sys_clk) if(sys_rst_n) begin
  if(system_display_status[35:32]!==system_display_status[3:0]) $fatal(1,"Torn return status");
  if(system_display_status[31:0]!=0) returns=returns+1;
 end
 initial begin
  #1;reset_n=1;#2;reset_n=0;#47;reset_n=1;
  #10013;reset_n=0;#81;reset_n=1;
  #20000;
  if(snapshots<50 || returns<500) $fatal(1,"Mailbox stopped after reset");
  $display("PASS coherent1158-bit50/33MHz status and36-bit video return under continuous changes and common reset");$finish;
 end
endmodule
