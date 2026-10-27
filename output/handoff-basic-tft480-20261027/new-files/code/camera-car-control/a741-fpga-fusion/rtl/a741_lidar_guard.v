`timescale 1ns/1ps
`default_nettype none
// Raw-range manual protection. No world pose, trig, map or planner.
module a741_lidar_guard #(parameter LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1,ROTATION_CLEAR_MM=521)(
    input wire clk,rst_n,ms_tick,stream_valid,point_valid,
    input wire [15:0] angle,distance,input wire [7:0] confidence,
    input wire signed [31:0] requested_left,requested_right,
    output wire stop,output wire [9:0] limit,
    output reg scan_valid,output reg [15:0] front,rear,nearest
);
    reg [15:0] last_angle,scan_front,scan_rear,scan_nearest,age;
    reg seen;reg [9:0] points;reg [11:0] coverage;
    wire wrap=seen && angle<last_angle;
    wire qualified=point_valid && angle<36000 && distance!=0 && confidence>=20;
    wire [16:0] shifted=LIDAR_CLOCKWISE!=0 ? 17'(LIDAR_ZERO)+17'd36000-{1'b0,angle}:
        {1'b0,angle}+17'd36000-17'(LIDAR_ZERO);
    wire [15:0] body_angle=16'(shifted>=36000 ? shifted-36000:shifted);
    wire in_front=body_angle<=4500 || body_angle>=31500;
    wire in_rear=body_angle>=13500 && body_angle<=22500;
    wire turning=requested_left!=requested_right;
    wire signed [32:0] sum=$signed({requested_left[31],requested_left})+$signed({requested_right[31],requested_right});
    assign stop=!scan_valid || nearest<=ROTATION_CLEAR_MM || (turning ? nearest<=ROTATION_CLEAR_MM:
        sum>0 ? front<=450:sum<0 ? rear<=500:1'b0);
    assign limit=stop ? 10'd0:turning ? 10'd80:sum>0 && front<=900 ? 10'd60:10'd400;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            seen<=0;last_angle<=0;scan_front<=65535;scan_rear<=65535;scan_nearest<=65535;
            front<=65535;rear<=65535;nearest<=65535;age<=65535;points<=0;coverage<=0;scan_valid<=0;
        end else begin
            if(ms_tick) begin if(age!=65535) age<=age+1'b1;if(age>=300) scan_valid<=0;end
            if(!stream_valid) begin
                seen<=0;points<=0;coverage<=0;scan_valid<=0;scan_front<=65535;scan_rear<=65535;scan_nearest<=65535;
                front<=65535;rear<=65535;nearest<=65535;
            end else if(qualified) begin
                seen<=1;last_angle<=angle;
                if(wrap) begin
                    front<=in_front && distance<scan_front ? distance:scan_front;
                    rear<=in_rear && distance<scan_rear ? distance:scan_rear;
                    nearest<=distance<scan_nearest ? distance:scan_nearest;
                    scan_valid<=points>=60 && &coverage && scan_front!=65535 && scan_rear!=65535;
                    age<=0;points<=1;coverage<=12'b1 << (angle/16'd3000);
                    scan_front<=in_front ? distance:16'd65535;scan_rear<=in_rear ? distance:16'd65535;scan_nearest<=distance;
                end else begin
                    if(points!=1023) points<=points+1'b1;
                    coverage[angle/16'd3000]<=1;
                    if(distance<scan_nearest) scan_nearest<=distance;
                    if(in_front && distance<scan_front) scan_front<=distance;
                    if(in_rear && distance<scan_rear) scan_rear<=distance;
                    if(distance<nearest) nearest<=distance;
                    if(in_front && distance<front) front<=distance;
                    if(in_rear && distance<rear) rear<=distance;
                end
            end
        end
endmodule
`default_nettype wire
