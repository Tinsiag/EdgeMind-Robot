`timescale 1ns/1ps
`default_nettype none
module acg720_camera_car_top(
    input wire clk,stop_n,
    input wire camera_pclk,camera_vsync,camera_href,input wire [7:0] camera_data,
    output wire camera_reset_n,inout wire camera_sclk,camera_sdat,
    input wire rgmii_rx_clk,input wire [3:0] rgmii_rxd,input wire rgmii_rx_ctl,
    output wire rgmii_tx_clk,output wire [3:0] rgmii_txd,output wire rgmii_tx_ctl,
    output wire eth_rst_n,eth_mdc,inout wire eth_mdio,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,output wire [7:0] led
);
    wire pll50,pll125,unused24,locked;
    Gowin_PLL clocks(.clkin(clk),.clkout0(pll50),.clkout1(pll125),.clkout2(unused24),
        .lock(locked),.mdclk(clk),.reset(!stop_n));
    wire global_n=stop_n && locked;
    wire control_n,net_n,rx_n,tx_n;
    reset_sync creset(.clk(clk),.async_n(global_n),.rst_n(control_n));
    reset_sync nreset(.clk(pll50),.async_n(global_n),.rst_n(net_n));
    reset_sync rxreset(.clk(rgmii_rx_clk),.async_n(global_n && eth_rst_n),.rst_n(rx_n));
    reset_sync txreset(.clk(pll125),.async_n(global_n),.rst_n(tx_n));
    wire camera_ready,camera_error,phy_ready;
    ov5640_board_init camera(.clk(clk),.rst_n(control_n),.camera_reset_n(camera_reset_n),
        .scl(camera_sclk),.sda(camera_sdat),.ready(camera_ready),.error(camera_error));
    phy_reg_config phy(.Clk(clk),.Rst_n(control_n),.Phy_rst_n(eth_rst_n),
        .Rd_Data(),.Phy_init_done(phy_ready),.mdc(eth_mdc),.mdio(eth_mdio));
    (* ASYNC_REG="TRUE" *) reg [1:0] camera_ready_sync;
    always @(posedge camera_pclk or negedge global_n)
        if(!global_n) camera_ready_sync<=0;
        else camera_ready_sync<={camera_ready_sync[0],camera_ready};
    (* ASYNC_REG="TRUE" *) reg [1:0] phy_ready_rx,phy_ready_tx;
    always @(posedge rgmii_rx_clk or negedge rx_n)
        if(!rx_n) phy_ready_rx<=0;
        else phy_ready_rx<={phy_ready_rx[0],phy_ready};
    always @(posedge pll125 or negedge tx_n)
        if(!tx_n) phy_ready_tx<=0;
        else phy_ready_tx<={phy_ready_tx[0],phy_ready};
    wire [7:0] gmii_rxd,gmii_txd;
    wire gmii_dv,gmii_er,gmii_en,gmii_txer;
    acg720_rgmii_rx receiver(.rx_clk(rgmii_rx_clk),.rxd(rgmii_rxd),.rx_ctl(rgmii_rx_ctl),
        .gmii_data(gmii_rxd),.gmii_valid(gmii_dv),.gmii_error(gmii_er));
    gmii_to_rgmii transmitter(.reset_n(global_n),.gmii_tx_clk(pll125),.gmii_txd(gmii_txd),
        .gmii_txen(gmii_en),.gmii_txer(gmii_txer),.rgmii_tx_clk(rgmii_tx_clk),
        .rgmii_txd(rgmii_txd),.rgmii_txen(rgmii_tx_ctl));
    wire [7:0] rx_data,tx_data;
    wire rx_valid,rx_last,rx_bad,rx_ready,tx_valid,tx_last,tx_bad,tx_ready;
    eth_mac_1g_fifo mac(.rx_clk(rgmii_rx_clk),.rx_rst(!rx_n),.tx_clk(pll125),.tx_rst(!tx_n),
        .logic_clk(pll50),.logic_rst(!net_n),
        .tx_axis_tdata(tx_data),.tx_axis_tkeep(1'b1),.tx_axis_tvalid(tx_valid),.tx_axis_tready(tx_ready),
        .tx_axis_tlast(tx_last),.tx_axis_tuser(tx_bad),
        .rx_axis_tdata(rx_data),.rx_axis_tvalid(rx_valid),.rx_axis_tready(rx_ready),
        .rx_axis_tlast(rx_last),.rx_axis_tuser(rx_bad),
        .gmii_rxd(gmii_rxd),.gmii_rx_dv(gmii_dv),.gmii_rx_er(gmii_er),
        .gmii_txd(gmii_txd),.gmii_tx_en(gmii_en),.gmii_tx_er(gmii_txer),
        .rx_clk_enable(1'b1),.tx_clk_enable(1'b1),.rx_mii_select(1'b0),.tx_mii_select(1'b0),
        .cfg_ifg(8'd12),.cfg_tx_enable(phy_ready_tx[1]),.cfg_rx_enable(phy_ready_rx[1]));
    wire raw_l1,raw_l2,raw_r1,raw_r2,camera_bad,camera_overflow;
    wire [7:0] motion_led;
    camera_ethernet_core #(.NET_CLK_HZ(50000000)) core(
        .clk_50m(clk),.stop_n(global_n),.net_clk(pll50),
        .eth_rx_data(rx_data),.eth_rx_valid(rx_valid),.eth_rx_last(rx_last),.eth_rx_bad(rx_bad),.eth_rx_ready(rx_ready),
        .eth_tx_data(tx_data),.eth_tx_valid(tx_valid),.eth_tx_last(tx_last),.eth_tx_bad(tx_bad),.eth_tx_ready(tx_ready),
        .cam_pclk(camera_pclk),.cam_ready(camera_ready_sync[1]),.cam_vsync(camera_vsync),
        .cam_href(camera_href),.cam_data(camera_data),
        .left_enc_a(left_enc_a),.left_enc_b(left_enc_b),.right_enc_a(right_enc_a),.right_enc_b(right_enc_b),
        .left_in1(raw_l1),.left_in2(raw_l2),.right_in1(raw_r1),.right_in2(raw_r2),
        .motion_led(motion_led),.camera_bad(camera_bad),.camera_overflow(camera_overflow));
    assign left_in1=global_n && raw_l1;
    assign left_in2=global_n && raw_l2;
    assign right_in1=global_n && raw_r1;
    assign right_in2=global_n && raw_r2;
    assign led={camera_error,camera_overflow,camera_bad,motion_led[6],motion_led[2],phy_ready,camera_ready,locked};
endmodule
`default_nettype wire
