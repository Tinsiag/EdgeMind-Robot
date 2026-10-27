`timescale 1ns/1ps
`default_nettype none
// AC620 reference: 50 MHz /10; 525x286; DE [42,522)x[11,283).
// Official controller changes data after RISING PCLK. AT043TN24 diagrams
// (PDF pp.13-14) sample on FALLING PCLK: allow 100 ns logical setup/hold.
module a741_tft480_panel #(parameter BACKLIGHT_FRAMES=6)(
 input wire clk,rst_n,input wire [15:0] rgb,
 output wire pixel_request,frame_blank,active,
 output wire [10:0] x,y,
 output reg tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl,
 output reg [15:0] tft_rgb
);
 reg [3:0] phase;
 reg [9:0] h;reg [8:0] v;
 localparam FRAME_BITS=$clog2(BACKLIGHT_FRAMES+1)>0 ? $clog2(BACKLIGHT_FRAMES+1):1;
 reg [FRAME_BITS-1:0] startup_frames;
 assign active=h>=42 && h<522 && v>=11 && v<283;
 assign x=h-10'd42;assign y=v-9'd11;
 assign pixel_request=phase==9 && active;
 assign frame_blank=phase==9 && h==0 && v==283;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin phase<=0;h<=0;v<=0;tft_clk<=0;tft_de<=0;tft_hsync<=0;
   tft_vsync<=0;tft_bl<=0;tft_rgb<=0;startup_frames<=0;end
  else begin
   phase<=phase==9 ? 4'd0:phase+1'b1;
   if(phase==4) tft_clk<=0;
   if(phase==9) begin
    tft_clk<=1;tft_de<=active;tft_hsync<=h>40;tft_vsync<=v>9;
    tft_rgb<=active ? rgb:16'd0;
    if(h==524) begin
     h<=0;
     if(v==285) begin
      v<=0;
      if(startup_frames<BACKLIGHT_FRAMES) startup_frames<=startup_frames+1'b1;
      if(BACKLIGHT_FRAMES==0 || startup_frames>=BACKLIGHT_FRAMES-1) tft_bl<=1;
     end else v<=v+1'b1;
    end else h<=h+1'b1;
   end
  end
endmodule
`default_nettype wire
