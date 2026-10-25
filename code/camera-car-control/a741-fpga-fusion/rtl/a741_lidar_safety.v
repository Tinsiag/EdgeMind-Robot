`timescale 1ns/1ps
`default_nettype none
// Independent of Ethernet and mapping. Old/incomplete scans never authorize motion.
module a741_lidar_safety #(parameter BODY_COORDINATES=0,FRONT_EXTENT=0,REAR_EXTENT=0,HALF_WIDTH=0)(
    input wire clk,rst_n,ms_tick,stream_valid,point_valid,scan_end,
    input wire [15:0] angle_cdeg,distance_mm,input wire [15:0] rotation_radius_mm,
    input wire signed [31:0] requested_left,requested_right,
    input wire signed [31:0] point_x,point_y,
    output wire stop,rotation_clear,output reg scan_valid,
    output reg [15:0] front_mm,rear_mm,min_mm,
    output wire [15:0] clearance_mm,output wire [9:0] speed_limit
);
    reg [15:0] scan_front,scan_rear,scan_min,age;
    reg [63:0] scan_rotation_min_sq,rotation_min_sq;
    reg [9:0] points;
    reg [11:0] coverage;
    reg [11:0] scaled_gap;
    reg [9:0] speed_cached;
    wire forward=$signed(requested_left)+$signed(requested_right)>0;
    wire reverse=$signed(requested_left)+$signed(requested_right)<0;
    wire turning=requested_left!=requested_right;
    wire [31:0] abs_x=point_x<0 ? -point_x:point_x,abs_y=point_y<0 ? -point_y:point_y;
    wire [31:0] body_radius=abs_x>abs_y ? abs_x:abs_y;
    // Use the exact squared distance for the swept rotational envelope.
    // This avoids a square-root datapath and keeps the safety comparison exact.
    wire [63:0] rotation_x_sq={32'd0,abs_x}*{32'd0,abs_x};
    wire [63:0] rotation_y_sq={32'd0,abs_y}*{32'd0,abs_y};
    wire [63:0] distance_sq={48'd0,distance_mm}*{48'd0,distance_mm};
    wire [63:0] rotation_point_sq=BODY_COORDINATES!=0 ?
        rotation_x_sq+rotation_y_sq:distance_sq;
    wire [31:0] rotation_limit={16'd0,rotation_radius_mm}+32'd100;
    wire [63:0] rotation_limit_sq={32'd0,rotation_limit}*{32'd0,rotation_limit};
    wire [15:0] point_min=BODY_COORDINATES!=0 ? (body_radius>65535 ? 16'd65535:body_radius[15:0]):distance_mm;
    wire in_front=BODY_COORDINATES!=0 ? (point_x>0 && abs_y<HALF_WIDTH+100):(angle_cdeg<3000 || angle_cdeg>33000);
    wire in_rear=BODY_COORDINATES!=0 ? (point_x<0 && abs_y<HALF_WIDTH+100):(angle_cdeg>15000 && angle_cdeg<21000);
    wire [15:0] front_gap=BODY_COORDINATES!=0 ? (point_x>FRONT_EXTENT ? 16'(point_x-FRONT_EXTENT):16'd0):distance_mm;
    wire [15:0] rear_gap=BODY_COORDINATES!=0 ? (-point_x>REAR_EXTENT ? 16'(-point_x-REAR_EXTENT):16'd0):distance_mm;
    assign clearance_mm=forward ? front_mm:reverse ? rear_mm:min_mm;
    assign rotation_clear=scan_valid && rotation_radius_mm!=0 && rotation_min_sq>rotation_limit_sq;
    assign stop=(!scan_valid || (turning ? !rotation_clear:clearance_mm<=250));
    assign speed_limit=!scan_valid || clearance_mm<=250 ? 0:clearance_mm>=600 ? 400:speed_cached;
    // 400/350 = 8/7. Narrow arithmetic and a register avoid a 32-bit
    // combinational divide from steering direction all the way into wheel PI.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin scaled_gap<=0;speed_cached<=0;end
        else begin
            scaled_gap<=clearance_mm>250 && clearance_mm<600 ? 12'(clearance_mm-16'd250)*12'd8:12'd0;
            speed_cached<=scaled_gap/12'd7;
        end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin scan_front<=65535;scan_rear<=65535;scan_min<=65535;age<=65535;points<=0;
            front_mm<=65535;rear_mm<=65535;min_mm<=65535;rotation_min_sq<=64'hffff_ffff_ffff_ffff;scan_rotation_min_sq<=64'hffff_ffff_ffff_ffff;scan_valid<=0;coverage<=0;end
        else begin
            if(ms_tick) begin if(age!=65535) age<=age+1'b1;if(age>=300) scan_valid<=0;end
            if(!stream_valid) begin scan_valid<=0;points<=0;coverage<=0;scan_front<=65535;scan_rear<=65535;scan_min<=65535;scan_rotation_min_sq<=64'hffff_ffff_ffff_ffff;end
            else if(point_valid) begin
                if(scan_end) begin
                    front_mm<=in_front && front_gap<scan_front ? front_gap:scan_front;
                    rear_mm<=in_rear && rear_gap<scan_rear ? rear_gap:scan_rear;
                    min_mm<=point_min<scan_min ? point_min:scan_min;
                    rotation_min_sq<=rotation_point_sq<scan_rotation_min_sq ? rotation_point_sq:scan_rotation_min_sq;
                    scan_valid<=points>=60 && &coverage && scan_front!=65535 && scan_rear!=65535;
                    // Projector marks the first point after angular wrap. It
                    // also belongs to the new scan, including its obstacle.
                    age<=0;points<=1;
                    coverage<=angle_cdeg<36000 ? (12'b1 << (angle_cdeg/16'd3000)):12'd0;
                    scan_front<=in_front ? front_gap:16'd65535;
                    scan_rear<=in_rear ? rear_gap:16'd65535;scan_min<=point_min;scan_rotation_min_sq<=rotation_point_sq;
                end else begin
                    if(points!=1023) points<=points+1'b1;
                    if(angle_cdeg<36000) coverage[angle_cdeg/16'd3000]<=1;
                    if(point_min<scan_min) scan_min<=point_min;
                    if(in_front && front_gap<scan_front) scan_front<=front_gap;
                    if(in_rear && rear_gap<scan_rear) scan_rear<=rear_gap;
                    // New nearby obstacles take effect before a full revolution.
                    if(in_front && front_gap<front_mm) front_mm<=front_gap;
                    if(in_rear && rear_gap<rear_mm) rear_mm<=rear_gap;
                    if(point_min<min_mm) min_mm<=point_min;
                    if(rotation_point_sq<rotation_min_sq) rotation_min_sq<=rotation_point_sq;
                    if(rotation_point_sq<scan_rotation_min_sq) scan_rotation_min_sq<=rotation_point_sq;
                end
            end
        end
endmodule
`default_nettype wire
