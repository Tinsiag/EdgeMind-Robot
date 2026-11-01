`timescale 1ns/1ps
`default_nettype none
// Capture the centered 640x480 window of the 800x480 display stream.
// pixel/x/y/active are cycle-aligned (video_pixels is combinational on
// shift[15:0]); one token per active display clock inside the window.
// Token = {sof, sol, y[9:0], rgb565}. Only one of every FRAME_DIV display
// frames is forwarded so the 50 MHz byte path keeps margin.
// Lines are written atomically: at the first pixel of a line the write-side
// FIFO occupancy is checked and the whole line is skipped if 640 tokens do
// not fit, so the FIFO never truncates a line. Missing camera pixels
// (pixel_valid=0) are sent as black to keep every line exactly W tokens.
module a745_video_capture_tx #(parameter FRAME_DIV=2,X0=80,W=640,H=480,DEPTH=8192,LEVEL_BITS=14)(
 input wire clk,rst_n,active,pixel_valid,
 input wire [10:0] x,input wire [10:0] y,input wire [15:0] pixel,
 input wire [LEVEL_BITS-1:0] wr_level,
 output wire [27:0] token,output wire valid,
 output reg [31:0] skipped_lines
);
 localparam DIV_BITS=FRAME_DIV>1 ? $clog2(FRAME_DIV):1;
 reg [DIV_BITS-1:0] phase;
 wire in_window=active && x>=X0 && x<X0+W && y<H;
 wire sol=x==X0;
 wire sof=sol && y==0;
 reg send,line_en;
 wire send_now=sof ? phase==0:send;
 // 8-token margin covers the registered level and pointer-sync lag.
 wire room=wr_level<=DEPTH-W-8;
 wire line_now=sol ? room:line_en;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin phase<=0;send<=0;line_en<=0;skipped_lines<=0;end
  else if(in_window) begin
   if(sof) begin
    send<=phase==0;
    phase<=(FRAME_DIV<=1 || phase==FRAME_DIV-1) ? {DIV_BITS{1'b0}}:phase+1'b1;
   end
   if(sol) begin
    line_en<=room;
    if(send_now && !room) skipped_lines<=skipped_lines+1'b1;
   end
  end
 assign valid=in_window && send_now && line_now;
 assign token={sof,sol,y[9:0],pixel_valid ? pixel:16'd0};
endmodule
`default_nettype wire
