`timescale 1ns/1ps
`default_nettype none
// Combinational pixel layer below the existing HUD; no extra scan latency.
module a745_detection_overlay #(parameter TTL_FRAMES=60)(
 input wire clk,rst_n,frame_blank,update,input wire [771:0] detections,
 input wire [10:0] x,y,input wire [15:0] pixel,output wire [15:0] rgb,
 output wire present
);
 reg [771:0] pending,current;
 reg pending_valid,blank_d;
 reg [6:0] age;
 reg edge_pixel;
 integer i;
 reg [15:0] left_x,right_x,top_y,bottom_y;
 assign present=current[3:0]!=0;
 always @(posedge clk or negedge rst_n)
 if(!rst_n) begin pending<=0;current<=0;pending_valid<=0;blank_d<=0;age<=0;end
 else begin
  blank_d<=frame_blank;
  if(update) begin pending<=detections;pending_valid<=1;end
  if(frame_blank && !blank_d) begin
   if(pending_valid) begin current<=pending;pending_valid<=update;age<=0;end
   else if(age<TTL_FRAMES) age<=age+1'b1;
   else current<=0;
  end
 end
 always @* begin
  edge_pixel=0;left_x=0;right_x=0;top_y=0;bottom_y=0;
  for(i=0;i<8;i=i+1) begin
   left_x=current[4+i*96+:16]+16'd80;top_y=current[20+i*96+:16];
   right_x=current[36+i*96+:16]+16'd80;bottom_y=current[52+i*96+:16];
   if(i<current[3:0] && x>=left_x && x<=right_x && y>=top_y && y<=bottom_y &&
      (x<left_x+2 || x+2>right_x || y<top_y+2 || y+2>bottom_y)) edge_pixel=1;
  end
 end
 assign rgb=edge_pixel ? 16'h07e0:pixel;
endmodule
`default_nettype wire
