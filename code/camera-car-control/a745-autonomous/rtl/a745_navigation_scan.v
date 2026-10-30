`timescale 1ns/1ps
`default_nettype none
// Complete-scan distances plus independent, CAD-derived left/right turn space.
// New close returns revoke a published clearance without waiting for a wrap.
module a745_navigation_scan #(parameter LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1)(
 input wire clk,rst_n,ms_tick,stream_valid,point_valid,
 input wire [15:0] angle,distance,input wire [7:0] confidence,
 output reg scan_valid,output reg [15:0] front,left,right,rear,
 output wire left_clear,right_clear,output reg [7:0] scan_sequence
);
 wire [16:0] shifted=LIDAR_CLOCKWISE!=0 ? 17'(LIDAR_ZERO)+17'd36000-{1'b0,angle}:
  {1'b0,angle}+17'd36000-17'(LIDAR_ZERO);
 reg valid1,valid2;
 reg [15:0] body1,body2,raw1,raw2,distance1,distance2;
 reg [6:0] bin;
 wire [8:0] left_limit,right_limit;
 a745_turn_envelope envelope(.bin(bin),.left_limit(left_limit),.right_limit(right_limit));
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin valid1<=0;valid2<=0;body1<=0;body2<=0;raw1<=0;raw2<=0;
   distance1<=0;distance2<=0;bin<=0;end
  else begin
   valid1<=stream_valid && point_valid && angle<36000 && distance!=0 && confidence>=20;
   valid2<=stream_valid && valid1;
   body1<=16'(shifted>=36000 ? shifted-36000:shifted);raw1<=angle;distance1<=distance;
   body2<=body1;raw2<=raw1;distance2<=distance1;bin<=7'(body1/16'd500);
  end
 reg seen,left_ok,right_ok,published_left,published_right;
 reg [15:0] last_angle,age,scan_front,scan_left,scan_right,scan_rear;
 reg [9:0] points;reg [11:0] coverage;
 wire wrap=seen && raw2<last_angle;
 wire in_front=body2<=3000 || body2>=33000;
 wire in_left=body2>=4500 && body2<=13500;
 wire in_right=body2>=22500 && body2<=31500;
 wire in_rear=body2>=13500 && body2<=22500;
 wire point_left_ok=distance2>{7'd0,left_limit};
 wire point_right_ok=distance2>{7'd0,right_limit};
 assign left_clear=scan_valid && published_left;
 assign right_clear=scan_valid && published_right;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   seen<=0;last_angle<=0;age<=65535;points<=0;coverage<=0;scan_valid<=0;scan_sequence<=0;
   front<=65535;left<=65535;right<=65535;rear<=65535;
   scan_front<=65535;scan_left<=65535;scan_right<=65535;scan_rear<=65535;
   left_ok<=1;right_ok<=1;published_left<=0;published_right<=0;
  end else if(!stream_valid) begin
   seen<=0;age<=65535;points<=0;coverage<=0;scan_valid<=0;
   front<=65535;left<=65535;right<=65535;rear<=65535;
   scan_front<=65535;scan_left<=65535;scan_right<=65535;scan_rear<=65535;
   left_ok<=1;right_ok<=1;published_left<=0;published_right<=0;
  end else begin
   if(ms_tick) begin
    if(age!=65535) age<=age+1'b1;
    if(age>=300) begin scan_valid<=0;published_left<=0;published_right<=0;end
   end
   if(valid2) begin
    seen<=1;last_angle<=raw2;
    if(wrap) begin
     scan_valid<=points>=60 && &coverage && scan_front!=65535 && scan_left!=65535 && scan_right!=65535 && scan_rear!=65535;
     front<=in_front && distance2<scan_front ? distance2:scan_front;
     left<=in_left && distance2<scan_left ? distance2:scan_left;
     right<=in_right && distance2<scan_right ? distance2:scan_right;
     rear<=in_rear && distance2<scan_rear ? distance2:scan_rear;
     published_left<=left_ok && point_left_ok;published_right<=right_ok && point_right_ok;
     age<=0;points<=1;coverage<=12'b1 << (raw2/16'd3000);scan_sequence<=scan_sequence+1'b1;
     scan_front<=in_front ? distance2:16'd65535;
     scan_left<=in_left ? distance2:16'd65535;
     scan_right<=in_right ? distance2:16'd65535;
     scan_rear<=in_rear ? distance2:16'd65535;
     left_ok<=point_left_ok;right_ok<=point_right_ok;
    end else begin
     if(points!=1023) points<=points+1'b1;
     coverage[raw2/16'd3000]<=1;
     if(in_front && distance2<scan_front) scan_front<=distance2;
     if(in_left && distance2<scan_left) scan_left<=distance2;
     if(in_right && distance2<scan_right) scan_right<=distance2;
     if(in_rear && distance2<scan_rear) scan_rear<=distance2;
     if(in_front && distance2<front) front<=distance2;
     if(in_left && distance2<left) left<=distance2;
     if(in_right && distance2<right) right<=distance2;
     if(in_rear && distance2<rear) rear<=distance2;
     if(!point_left_ok) begin left_ok<=0;published_left<=0;end
     if(!point_right_ok) begin right_ok<=0;published_right<=0;end
    end
   end
  end
endmodule
`default_nettype wire
