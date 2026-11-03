`timescale 1ns/1ps
`default_nettype none
module a745_path_guard #(parameter LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1)(
 input wire clk,rst_n,stream_valid,scan_valid,point_valid,
 input wire [15:0] angle,distance,input wire [7:0] confidence,
 output wire advance_clear,reverse_clear,left_exit_clear,right_exit_clear,spin_clear
);
 wire [16:0] shifted=LIDAR_CLOCKWISE ? 17'(LIDAR_ZERO)+36000-{1'b0,angle}:{1'b0,angle}+36000-17'(LIDAR_ZERO);
 reg v1,v2;reg [15:0] a1,a2,d1,d2,last_angle,body1;reg [6:0] bin;reg seen;
 reg [4:0] accumulating,published;reg [9:0] points;reg [11:0] coverage;
 wire [9:0] advance_limit,reverse_limit,left_exit_limit,right_exit_limit,spin_limit;
 a745_path_envelope rom(.*);
 wire [4:0] clear_point={d2>spin_limit,d2>right_exit_limit,d2>left_exit_limit,d2>reverse_limit,d2>advance_limit};
 assign {spin_clear,right_exit_clear,left_exit_clear,reverse_clear,advance_clear}=published & {5{scan_valid && stream_valid}};
 always @(posedge clk or negedge rst_n)
 if(!rst_n)begin v1<=0;v2<=0;a1<=0;a2<=0;d1<=0;d2<=0;body1<=0;bin<=0;last_angle<=0;seen<=0;accumulating<=31;published<=0;points<=0;coverage<=0;end
 else begin
  v1<=stream_valid && point_valid && angle<36000 && distance!=0 && confidence>=20;
  v2<=v1 && stream_valid;a1<=angle;a2<=a1;d1<=distance;d2<=d1;
  body1<=16'(shifted>=36000 ? shifted-36000:shifted);bin<=7'(body1/500);
  // ROM bin and d1 are both captured from the same input point.
  if(!stream_valid)begin published<=0;accumulating<=31;seen<=0;points<=0;coverage<=0;end
  else if(v2)begin
   seen<=1;last_angle<=a2;
   if(seen && a2<last_angle)begin
    published<=points>=60 && (&coverage) ? accumulating & clear_point:5'd0;
    accumulating<=clear_point;points<=1;coverage<=12'b1 << (a2/3000);
   end else begin
    accumulating<=accumulating & clear_point;published<=published & clear_point;
    if(points!=1023)points<=points+1'b1;coverage[a2/3000]<=1;
   end
  end
 end
endmodule
`default_nettype wire
