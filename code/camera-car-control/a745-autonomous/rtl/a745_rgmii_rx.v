`timescale 1ns/1ps
`default_nettype none
// RTL8211F RX internal clock delay is enabled/read back by PHY configuration.
module a745_rgmii_rx(input wire clk,input wire [3:0] data,input wire ctl,
 output wire [7:0] gmii_data,output wire gmii_valid,gmii_error);
 wire rise_ctl,fall_ctl;
 wire [4:0] delayed;
 genvar i;
 generate for(i=0;i<4;i=i+1) begin: lanes
  IODELAY #(.C_STATIC_DLY(96),.DYN_DLY_EN("FALSE"),.ADAPT_EN("FALSE")) delay(
    .DI(data[i]),.DO(delayed[i]),.DF(),.DLYSTEP(8'd0),.SDTAP(1'b0),.VALUE(1'b0));
  IDDR sample(.CLK(clk),.D(delayed[i]),.Q0(gmii_data[i]),.Q1(gmii_data[i+4]));
 end endgenerate
 IODELAY #(.C_STATIC_DLY(96),.DYN_DLY_EN("FALSE"),.ADAPT_EN("FALSE")) control_delay(
    .DI(ctl),.DO(delayed[4]),.DF(),.DLYSTEP(8'd0),.SDTAP(1'b0),.VALUE(1'b0));
 IDDR control_sample(.CLK(clk),.D(delayed[4]),.Q0(rise_ctl),.Q1(fall_ctl));
 assign gmii_valid=rise_ctl;
 assign gmii_error=rise_ctl^fall_ctl;
endmodule
`default_nettype wire
