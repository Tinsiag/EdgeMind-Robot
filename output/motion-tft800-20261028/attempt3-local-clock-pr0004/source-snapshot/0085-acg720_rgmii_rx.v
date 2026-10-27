`timescale 1ns/1ps
`default_nettype none
// Manufacturer chapter 58/59 IDDR pin mapping, with RX_CTL decoded for a MAC.
module acg720_rgmii_rx #(parameter INPUT_DELAY_TAPS=0)(
    input wire rx_clk,input wire [3:0] rxd,input wire rx_ctl,
    output wire [7:0] gmii_data,output wire gmii_valid,gmii_error
);
    wire ctl_rise,ctl_fall;
    wire [4:0] pins={rx_ctl,rxd};
    wire [4:0] sampled;
    genvar i;
    generate for(i=0;i<5;i=i+1) begin: input_delay
        if(INPUT_DELAY_TAPS==0) assign sampled[i]=pins[i];
        else IODELAY #(.C_STATIC_DLY(INPUT_DELAY_TAPS),.DYN_DLY_EN("FALSE"),.ADAPT_EN("FALSE")) delay(
            .DI(pins[i]),.DO(sampled[i]),.DF(),.DLYSTEP(8'd0),.SDTAP(1'b0),.VALUE(1'b0));
    end endgenerate
    generate for(i=0;i<4;i=i+1) begin: bits
        IDDR capture(.Q0(gmii_data[i]),.Q1(gmii_data[i+4]),.D(sampled[i]),.CLK(rx_clk));
    end endgenerate
    IDDR control(.Q0(ctl_rise),.Q1(ctl_fall),.D(sampled[4]),.CLK(rx_clk));
    assign gmii_valid=ctl_rise;
    assign gmii_error=ctl_rise ^ ctl_fall;
endmodule
`default_nettype wire
