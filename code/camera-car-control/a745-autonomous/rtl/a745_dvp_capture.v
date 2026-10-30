`timescale 1ns/1ps
`default_nettype none
// Registered DVP pad bundle, like chapter45 DVP_Capture. Start only at a real
// frame boundary, and accept a last HREF fall coincident with VSYNC assertion.
module a745_dvp_capture #(parameter WIDTH=800,HEIGHT=480,SKIP_FRAMES=10)(
 input wire pclk,rst_n,enable,vsync,href,input wire [7:0] data,
 output reg pixel_valid,output reg [15:0] pixel,
 output reg frame_start,frame_end,frame_good,frame_error
);
 reg vs,hs;reg [7:0] d;reg previous_vs,previous_hs,active,half_byte,bad,saw_blank;
 reg [7:0] high_byte;reg [11:0] column,row;reg [19:0] pixels;reg [7:0] skipped;
 wire last_line_closed=previous_hs && !hs && !half_byte && column==WIDTH;
 wire complete_rows=(row==HEIGHT && column==0) || (row==HEIGHT-1 && last_line_closed);
 always @(posedge pclk) begin vs<=vsync;hs<=href;d<=data;end
 always @(posedge pclk or negedge rst_n)
  if(!rst_n) begin
   previous_vs<=1;previous_hs<=0;active<=0;half_byte<=0;bad<=0;saw_blank<=0;
   high_byte<=0;column<=0;row<=0;pixels<=0;skipped<=0;
   pixel_valid<=0;pixel<=0;frame_start<=0;frame_end<=0;frame_good<=0;frame_error<=0;
  end else begin
   previous_vs<=vs;previous_hs<=hs;pixel_valid<=0;frame_start<=0;frame_end<=0;
   if(!enable) begin active<=0;half_byte<=0;skipped<=0;saw_blank<=0;end
   else begin
    if(vs) saw_blank<=1;
    if(saw_blank && previous_vs && !vs) begin
     active<=1;column<=0;row<=0;pixels<=0;bad<=0;half_byte<=hs;high_byte<=d;
     frame_start<=1;frame_good<=0;frame_error<=0;
    end else if(!previous_vs && vs && active) begin
     active<=0;frame_end<=1;half_byte<=0;
     frame_error<=bad || half_byte || hs || !complete_rows || pixels!=WIDTH*HEIGHT;
     frame_good<=!bad && !half_byte && !hs && complete_rows && pixels==WIDTH*HEIGHT && skipped>=SKIP_FRAMES;
     if(!bad && !half_byte && !hs && complete_rows && pixels==WIDTH*HEIGHT && skipped<SKIP_FRAMES) skipped<=skipped+1'b1;
    end else if(active && !vs) begin
     if(previous_hs && !hs) begin
      if(half_byte || column!=WIDTH || row>=HEIGHT) bad<=1;
      column<=0;half_byte<=0;if(row<4095) row<=row+1'b1;else bad<=1;
     end
     if(hs) begin
      if(!half_byte) begin high_byte<=d;half_byte<=1;end
      else begin
       half_byte<=0;
       if(column<WIDTH && row<HEIGHT) begin pixel<={high_byte,d};pixel_valid<=1;end
       else bad<=1;
       if(column<4095) column<=column+1'b1;else bad<=1;
       if(pixels<WIDTH*HEIGHT+1) pixels<=pixels+1'b1;else bad<=1;
      end
     end
    end
   end
  end
endmodule
`default_nettype wire
