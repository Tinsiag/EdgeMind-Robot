`timescale 1ns/1ps
`default_nettype none
// Integration core, not a pin-constrained RJ45 board top.
// Camera SCCB/24MHz clock and Ethernet MAC/PHY belong to the platform wrapper.
module camera_motion_core #(
    parameter WIDTH=800,HEIGHT=480,SKIP_FRAMES=10,FIFO_ADDR_BITS=13
)(
    input wire clk_50m,stop_n,uart_rx,
    output wire uart_tx,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,
    output wire [7:0] motion_led,
    input wire cam_pclk,cam_ready,cam_vsync,cam_href,
    input wire [7:0] cam_data,
    input wire net_clk,net_ready,
    output wire [7:0] video_udp_data,
    output wire video_udp_valid,video_udp_start,video_udp_last,
    output wire [15:0] video_udp_length,
    output wire camera_bad,camera_overflow
);
    wire motion_rst_n,cam_rst_n,net_rst_n;
    reset_sync r0(.clk(clk_50m),.async_n(stop_n),.rst_n(motion_rst_n));
    reset_sync r1(.clk(cam_pclk),.async_n(stop_n),.rst_n(cam_rst_n));
    reset_sync r2(.clk(net_clk),.async_n(stop_n),.rst_n(net_rst_n));
    motion_sync_top motion(
        .clk(clk_50m),.stop_n(motion_rst_n),.uart_rx(uart_rx),.uart_tx(uart_tx),
        .left_enc_a(left_enc_a),.left_enc_b(left_enc_b),
        .right_enc_a(right_enc_a),.right_enc_b(right_enc_b),
        .left_in1(left_in1),.left_in2(left_in2),.right_in1(right_in1),.right_in2(right_in2),
        .led(motion_led)
    );
    wire pixel_valid,frame_start,frame_end,frame_good;
    wire [15:0] pixel;
    dvp_capture_continuous #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.SKIP_FRAMES(SKIP_FRAMES)) capture(
        .pclk(cam_pclk),.rst_n(cam_rst_n),.enable(cam_ready),
        .vsync(cam_vsync),.href(cam_href),.data(cam_data),
        .pixel_valid(pixel_valid),.pixel(pixel),.pixel_x(),.pixel_y(),
        .frame_start(frame_start),.frame_end(frame_end),.frame_good(frame_good),.frame_error(camera_bad)
    );
    wire fifo_write,fifo_full,fifo_empty,fifo_read;
    wire [17:0] fifo_input,fifo_output;
    capture_tokens tokens(.clk(cam_pclk),.rst_n(cam_rst_n),.frame_start(frame_start),
        .frame_end(frame_end),.frame_good(frame_good),.pixel_valid(pixel_valid),.pixel(pixel),
        .fifo_full(fifo_full),.fifo_write(fifo_write),.fifo_data(fifo_input),.overflow(camera_overflow));
    async_fifo #(.WIDTH(18),.ADDR_BITS(FIFO_ADDR_BITS)) fifo(
        .wr_clk(cam_pclk),.wr_rst_n(cam_rst_n),.wr_en(fifo_write),.wr_data(fifo_input),.full(fifo_full),
        .rd_clk(net_clk),.rd_rst_n(net_rst_n),.rd_en(fifo_read),.rd_data(fifo_output),.empty(fifo_empty)
    );
    video_udp_packetizer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) packetizer(
        .clk(net_clk),.rst_n(net_rst_n),.token_data(fifo_output),.token_empty(fifo_empty),.token_read(fifo_read),
        .udp_data(video_udp_data),.udp_valid(video_udp_valid),.udp_start(video_udp_start),
        .udp_last(video_udp_last),.udp_length(video_udp_length),.udp_ready(net_ready)
    );
endmodule
`default_nettype wire
