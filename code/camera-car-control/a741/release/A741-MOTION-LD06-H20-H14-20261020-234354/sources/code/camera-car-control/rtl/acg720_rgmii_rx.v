`timescale 1ns/1ps
`default_nettype none
// Manufacturer chapter 58/59 IDDR pin mapping, with RX_CTL decoded for a MAC.
module acg720_rgmii_rx(
    input wire rx_clk,input wire [3:0] rxd,input wire rx_ctl,
    output wire [7:0] gmii_data,output wire gmii_valid,gmii_error
);
    wire ctl_rise,ctl_fall;
    genvar i;
    generate for(i=0;i<4;i=i+1) begin: bits
        IDDR capture(.Q0(gmii_data[i]),.Q1(gmii_data[i+4]),.D(rxd[i]),.CLK(rx_clk));
    end endgenerate
    IDDR control(.Q0(ctl_rise),.Q1(ctl_fall),.D(rx_ctl),.CLK(rx_clk));
    assign gmii_valid=ctl_rise;
    assign gmii_error=ctl_rise ^ ctl_fall;
endmodule
`default_nettype wire
