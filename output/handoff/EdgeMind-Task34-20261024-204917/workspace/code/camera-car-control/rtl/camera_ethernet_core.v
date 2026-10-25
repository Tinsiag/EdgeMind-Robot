`timescale 1ns/1ps
`default_nettype none
// Both video and control share an Ethernet MAC. No external serial module.
module camera_ethernet_core #(
    parameter WIDTH=800,HEIGHT=480,SKIP_FRAMES=10,NET_CLK_HZ=125000000
)(
    input wire clk_50m,stop_n,net_clk,
    input wire [7:0] eth_rx_data,input wire eth_rx_valid,eth_rx_last,eth_rx_bad,
    output wire eth_rx_ready,
    output wire [7:0] eth_tx_data,output wire eth_tx_valid,eth_tx_last,eth_tx_bad,
    input wire eth_tx_ready,
    input wire cam_pclk,cam_ready,cam_vsync,cam_href,input wire [7:0] cam_data,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,
    output wire [7:0] motion_led,output wire camera_bad,camera_overflow
);
    wire net_rst_n;
    reset_sync nr(.clk(net_clk),.async_n(stop_n),.rst_n(net_rst_n));
    wire uart_to_motion,uart_from_motion;
    wire [7:0] video_data,crx,ctx;
    wire video_valid,video_last,video_ready,crv,crl,crb,crr,ctv,ctl,ctr;
    wire [15:0] video_length,control_length;
    camera_motion_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.SKIP_FRAMES(SKIP_FRAMES)) camera_motion(
        .clk_50m(clk_50m),.stop_n(stop_n),.uart_rx(uart_to_motion),.uart_tx(uart_from_motion),
        .left_enc_a(left_enc_a),.left_enc_b(left_enc_b),.right_enc_a(right_enc_a),.right_enc_b(right_enc_b),
        .left_in1(left_in1),.left_in2(left_in2),.right_in1(right_in1),.right_in2(right_in2),.motion_led(motion_led),
        .cam_pclk(cam_pclk),.cam_ready(cam_ready),.cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),
        .net_clk(net_clk),.net_ready(video_ready),.video_udp_data(video_data),.video_udp_valid(video_valid),
        .video_udp_start(),.video_udp_last(video_last),.video_udp_length(video_length),
        .camera_bad(camera_bad),.camera_overflow(camera_overflow));
    udp_uart_control #(.CLK_HZ(NET_CLK_HZ)) control(
        .clk(net_clk),.rst_n(net_rst_n),.rx_data(crx),.rx_valid(crv),.rx_last(crl),.rx_bad(crb),.rx_ready(crr),
        .tx_data(ctx),.tx_valid(ctv),.tx_first(),.tx_last(ctl),.tx_length(control_length),.tx_ready(ctr),
        .motion_uart_rx(uart_to_motion),.motion_uart_tx(uart_from_motion),.rejected());
    ethernet_udp_router network(
        .clk(net_clk),.rst_n(net_rst_n),.eth_rx_data(eth_rx_data),.eth_rx_valid(eth_rx_valid),
        .eth_rx_last(eth_rx_last),.eth_rx_bad(eth_rx_bad),.eth_rx_ready(eth_rx_ready),
        .eth_tx_data(eth_tx_data),.eth_tx_valid(eth_tx_valid),.eth_tx_last(eth_tx_last),
        .eth_tx_bad(eth_tx_bad),.eth_tx_ready(eth_tx_ready),
        .control_rx_data(crx),.control_rx_valid(crv),.control_rx_last(crl),.control_rx_bad(crb),.control_rx_ready(crr),
        .control_tx_data(ctx),.control_tx_valid(ctv),.control_tx_last(ctl),.control_tx_length(control_length),.control_tx_ready(ctr),
        .video_data(video_data),.video_valid(video_valid),.video_last(video_last),.video_length(video_length),.video_ready(video_ready));
endmodule
`default_nettype wire
