`timescale 1ns/1ps
`default_nettype none
// ACG720 chapter28 HW_TFT50 and TFT_V3.0 manual: 1056x525, 800x480.
// Feed a real 33MHz PLL clock. RGB/DE launch on clk rising; forwarded PCLK
// is inverted, centering the WKS43189 rising-edge sample in stable data.
// Two pixel pipeline stages match a741_osd PIPELINED=1. No fractional clock.
module a741_tft800_panel #(parameter BACKLIGHT_FRAMES=12)(
 input wire clk,rst_n,input wire [15:0] rgb,
 output wire pixel_request,frame_blank,active,output wire [10:0] x,y,
 output wire tft_clk,output reg tft_de,tft_hsync,tft_vsync,tft_bl,
 output reg [15:0] tft_rgb
);
 reg [10:0] h;reg [9:0] v;
 reg [1:0] de_pipe,hs_pipe,vs_pipe;
 localparam FRAME_BITS=$clog2(BACKLIGHT_FRAMES+1)>0 ? $clog2(BACKLIGHT_FRAMES+1):1;
 reg [FRAME_BITS-1:0] startup_frames;
 assign tft_clk=~clk;
 assign active=h>=215 && h<1015 && v>=34 && v<514;
 assign x=h-11'd215;assign y={1'b0,v}-11'd34;
 assign pixel_request=active;
 assign frame_blank=h==0 && v==514;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   h<=0;v<=0;de_pipe<=0;hs_pipe<=0;vs_pipe<=0;
   tft_de<=0;tft_hsync<=0;tft_vsync<=0;tft_bl<=0;tft_rgb<=0;startup_frames<=0;
  end else begin
   de_pipe<={de_pipe[0],active};hs_pipe<={hs_pipe[0],h>=128};vs_pipe<={vs_pipe[0],v>=2};
   tft_de<=de_pipe[1];tft_hsync<=hs_pipe[1];tft_vsync<=vs_pipe[1];
   tft_rgb<=de_pipe[1] ? rgb:16'd0;
   if(h==1055) begin
    h<=0;
    if(v==524) begin
     v<=0;
     if(startup_frames<BACKLIGHT_FRAMES) startup_frames<=startup_frames+1'b1;
     if(BACKLIGHT_FRAMES==0 || startup_frames>=BACKLIGHT_FRAMES-1) tft_bl<=1;
    end else v<=v+1'b1;
   end else h<=h+1'b1;
  end
endmodule
`default_nettype wire
