`timescale 1ns/1ps
`default_nettype none
// Streaming LD06 near-return qualification, informed by the manufacturer's
// Tofbf::NearFilter: <5m weak groups need three adjacent, range-consistent
// samples; a strong singleton remains usable. Raw UDP packets are untouched.
// Two-point lookahead preserves every member of a qualifying triple, including
// across packet/raw-angle wrap boundaries. Invalid points break the group.
module a745_lidar_filter #(
 parameter MIN_CONFIDENCE=20,SINGLE_CONFIDENCE=220,NEAR_MM=5000,MAX_GAP_CDEG=250
)(
 input wire clk,rst_n,stream_valid,point_valid,
 input wire [15:0] angle,distance,input wire [7:0] confidence,
 output reg filtered_valid,output reg [15:0] filtered_angle,filtered_distance,
 output reg [7:0] filtered_confidence
);
 reg [15:0] angle0,angle1,distance0,distance1;
 reg [7:0] confidence0,confidence1;
 reg [1:0] count;reg [2:0] joins;
 wire usable=angle<36000 && distance!=0 && confidence>=MIN_CONFIDENCE;
 wire previous_usable=angle0<36000 && distance0!=0 && confidence0>=MIN_CONFIDENCE;
 wire center_usable=angle1<36000 && distance1!=0 && confidence1>=MIN_CONFIDENCE;
 wire [16:0] gap=angle>=angle0 ? {1'b0,angle}-{1'b0,angle0}:
  {1'b0,angle}+17'd36000-{1'b0,angle0};
 wire [15:0] difference=distance>=distance0 ? distance-distance0:distance0-distance;
 wire [22:0] difference_percent={7'd0,difference}*23'd100;
 wire [22:0] tolerance={7'd0,distance0}*23'd3;
 // 2.5 degrees bounds adjacent samples throughout the specified 5..13Hz
 // LD06 range (4500 points/s), while breaking missing-sector connections.
 wire join_next=count!=0 && usable && previous_usable && distance<NEAR_MM && distance0<NEAR_MM &&
  gap!=0 && gap<=MAX_GAP_CDEG && difference_percent<=tolerance;
 wire supported=(joins[2] && joins[1]) || (joins[1] && joins[0]) || (joins[0] && join_next);
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   filtered_valid<=0;filtered_angle<=0;filtered_distance<=0;filtered_confidence<=0;
   angle0<=0;angle1<=0;distance0<=0;distance1<=0;confidence0<=0;confidence1<=0;count<=0;joins<=0;
  end else begin
   filtered_valid<=0;
   if(!stream_valid) begin count<=0;joins<=0;filtered_confidence<=0;end
   else if(point_valid) begin
    filtered_valid<=count>=2;
    filtered_angle<=angle1;filtered_distance<=distance1;
    filtered_confidence<=center_usable &&
     (distance1>=NEAR_MM || confidence1>=SINGLE_CONFIDENCE || supported) ? confidence1:8'd0;
    angle1<=angle0;distance1<=distance0;confidence1<=confidence0;
    angle0<=angle;distance0<=distance;confidence0<=confidence;
    if(count<2) count<=count+1'b1;
    joins<={joins[1:0],join_next};
   end
  end
endmodule
`default_nettype wire
