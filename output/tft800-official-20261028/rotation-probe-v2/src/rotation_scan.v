`timescale 1ns/1ps
// User-requested 90 degree clockwise comparison. Mode0 rotates/scales the
// pattern within the documented800x480 raster; mode1 transposes BOTH raster
// axes (including blanking) to480x800. Mode1 is an unverified panel experiment.
module rotation_scan #(parameter MODE_FRAMES=480)(
 input wire clk50M,reset_n, output wire [15:0] TFT_rgb,
 output reg TFT_hs,TFT_vs,TFT_de, output wire TFT_clk,TFT_pwm,
 output wire portrait
);
 wire pclk,locked;
 reg portrait_q=0;
 assign portrait=portrait_q;
 Gowin_PLL Gowin_PLL(.clkin(clk50M),.clkout0(pclk),.lock(locked),.mdclk(clk50M),.reset(~reset_n));
 (* ASYNC_REG="TRUE" *) reg [1:0] tft_ready;
 always @(posedge pclk or negedge locked)
  if(!locked) tft_ready<=0;else tft_ready<={tft_ready[0],1'b1};
 wire ready=tft_ready[1];
 reg [10:0] h=0,v=0;reg [8:0] mode_frames=0;
 wire [10:0] ht=portrait ? 11'd525:11'd1056;
 wire [10:0] vt=portrait ? 11'd1056:11'd525;
 wire [10:0] hs=portrait ? 11'd2:11'd128;
 wire [10:0] vs=portrait ? 11'd128:11'd2;
 wire [10:0] hb=portrait ? 11'd34:11'd215;
 wire [10:0] vb=portrait ? 11'd215:11'd34;
 wire [10:0] width=portrait ? 11'd480:11'd800;
 wire [10:0] height=portrait ? 11'd800:11'd480;
 wire active=(h>=hb && h<hb+width && v>=vb && v<vb+height);
 wire [10:0] x=h-hb,y=v-vb;
 wire [10:0] column_width=portrait ? 11'd120:11'd200;
 wire [10:0] half_height=portrait ? 11'd400:11'd240;
 wire [1:0] column=(x<column_width) ? 0:(x<(column_width<<1)) ? 1:(x<(column_width*3)) ? 2:3;
 wire bottom=y>=half_height;
 reg [15:0] color,rgb=0;
 // Original 2columns x4rows clockwise ->4columns x2rows:
 // yellow green red black / white cyan purple blue.
 always @* begin
  case({bottom,column})
   0:color=16'hffe0;1:color=16'h07e0;2:color=16'hf800;3:color=16'h0000;
   4:color=16'hffff;5:color=16'h07ff;6:color=16'hf81f;7:color=16'h001f;
  endcase
 end
 always @(posedge pclk) begin
  if(!ready) begin
   h<=0;v<=0;portrait_q<=0;mode_frames<=0;rgb<=0;TFT_de<=0;TFT_hs<=0;TFT_vs<=0;
  end else begin
   TFT_de<=active;TFT_hs<=h>=hs;TFT_vs<=v>=vs;rgb<=active ? color:16'd0;
   if(h==ht-1) begin
    h<=0;
    if(v==vt-1) begin
     v<=0;
     if(mode_frames==MODE_FRAMES-1) begin mode_frames<=0;portrait_q<=~portrait;end
     else mode_frames<=mode_frames+1'b1;
    end else v<=v+1'b1;
   end else h<=h+1'b1;
  end
 end
 assign TFT_clk=pclk;assign TFT_pwm=1'b1;assign TFT_rgb=rgb;
endmodule
