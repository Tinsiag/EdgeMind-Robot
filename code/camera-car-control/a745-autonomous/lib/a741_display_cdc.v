`timescale 1ns/1ps
`default_nettype none
// Both reset synchronizers are driven by the same board/display PLL reset.
// Mailboxes hold the complete payload until acknowledged; no torn counters or
// independently synchronized bits in an IMU/CPU snapshot.
module a741_display_cdc(
 input wire sys_clk,sys_rst_n,disp_clk,disp_rst_n,
 input wire [895:0] status_snapshot,input wire [255:0] fusion_snapshot,
 input wire [5:0] system_flags,input wire [35:0] display_status,
 output wire [895:0] display_snapshot,output wire [255:0] display_fusion,
 output wire [5:0] display_flags,output wire display_update,
 output wire [35:0] system_display_status
);
 cdc_mailbox #(.WIDTH(1158)) to_display(
  .src_clk(sys_clk),.src_rst_n(sys_rst_n),.src_valid(1'b1),
  .src_data({system_flags,fusion_snapshot,status_snapshot}),.src_ready(),
  .dst_clk(disp_clk),.dst_rst_n(disp_rst_n),.dst_valid(display_update),
  .dst_data({display_flags,display_fusion,display_snapshot}));
 cdc_mailbox #(.WIDTH(36)) to_system(
  .src_clk(disp_clk),.src_rst_n(disp_rst_n),.src_valid(1'b1),
  .src_data(display_status),.src_ready(),
  .dst_clk(sys_clk),.dst_rst_n(sys_rst_n),.dst_valid(),.dst_data(system_display_status));
endmodule
`default_nettype wire
