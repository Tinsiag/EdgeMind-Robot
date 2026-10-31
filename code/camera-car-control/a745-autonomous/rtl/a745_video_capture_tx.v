`timescale 1ns/1ps
`default_nettype none
// Capture the centered 640x480 window from the existing 800x480 display stream.
// Tokens cross into the control clock through the existing async_fifo.
module a745_video_capture_tx(
 input wire clk,rst_n,active,pixel_valid,
 input wire [10:0] x,input wire [10:0] y,input wire [15:0] pixel,
 output wire [17:0] token,output wire valid
);
 assign valid=active && pixel_valid && x>=11'd80 && x<11'd720 && y<11'd480;
 assign token={2'b00,pixel};
endmodule
`default_nettype wire
