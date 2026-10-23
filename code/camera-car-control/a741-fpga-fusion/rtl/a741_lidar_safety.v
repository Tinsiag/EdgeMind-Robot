`timescale 1ns/1ps
`default_nettype none
// Independent of Ethernet and mapping. Old/incomplete scans never authorize motion.
module a741_lidar_safety(
    input wire clk,rst_n,ms_tick,stream_valid,point_valid,scan_end,
    input wire [15:0] angle_cdeg,distance_mm,input wire [15:0] rotation_radius_mm,
    input wire signed [31:0] requested_left,requested_right,
    output wire stop,rotation_clear,output reg scan_valid,
    output reg [15:0] front_mm,rear_mm,min_mm,
    output wire [15:0] clearance_mm,output wire [9:0] speed_limit
);
    reg [15:0] scan_front,scan_rear,scan_min,age;
    reg [9:0] points;
    reg [11:0] coverage;
    reg [11:0] scaled_gap;
    reg [9:0] speed_cached;
    wire forward=$signed(requested_left)+$signed(requested_right)>0;
    wire reverse=$signed(requested_left)+$signed(requested_right)<0;
    wire turning=(requested_left<0 && requested_right>0)||(requested_right<0 && requested_left>0);
    assign clearance_mm=forward ? front_mm:reverse ? rear_mm:min_mm;
    assign rotation_clear=scan_valid && rotation_radius_mm!=0 && min_mm>rotation_radius_mm+100;
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
            front_mm<=65535;rear_mm<=65535;min_mm<=65535;scan_valid<=0;coverage<=0;end
        else begin
            if(ms_tick) begin if(age!=65535) age<=age+1'b1;if(age>=300) scan_valid<=0;end
            if(!stream_valid) begin scan_valid<=0;points<=0;coverage<=0;scan_front<=65535;scan_rear<=65535;scan_min<=65535;end
            else if(point_valid) begin
                if(scan_end) begin
                    front_mm<=scan_front;rear_mm<=scan_rear;min_mm<=scan_min;
                    scan_valid<=points>=60 && &coverage && scan_front!=65535 && scan_rear!=65535;
                    age<=0;points<=0;coverage<=0;scan_front<=65535;scan_rear<=65535;scan_min<=65535;
                end else begin
                    if(points!=1023) points<=points+1'b1;
                    if(angle_cdeg<36000) coverage[angle_cdeg/16'd3000]<=1;
                    if(distance_mm<scan_min) scan_min<=distance_mm;
                    if((angle_cdeg<3000 || angle_cdeg>33000) && distance_mm<scan_front) scan_front<=distance_mm;
                    if(angle_cdeg>15000 && angle_cdeg<21000 && distance_mm<scan_rear) scan_rear<=distance_mm;
                end
                // A newly observed nearby obstacle is acted upon before a full revolution.
                if((angle_cdeg<3000 || angle_cdeg>33000) && distance_mm<front_mm) front_mm<=distance_mm;
                if(angle_cdeg>15000 && angle_cdeg<21000 && distance_mm<rear_mm) rear_mm<=distance_mm;
                if(distance_mm<min_mm) min_mm<=distance_mm;
            end
        end
endmodule
`default_nettype wire
