`timescale 1ns/1ps
`default_nettype none
// Fail-closed navigation authorization and bounded yaw-search recovery.
module a741_nav_guard #(parameter FRONT_STOP_MM=250,FRONT_SLOW_MM=600,SEARCH_SPEED_MM_S=40,ALLOW_REPLAN=0)(
    input wire clk,rst_n,tick,start,cancel,clear_fault,
    input wire geometry_verified,map_valid,pose_valid,lidar_valid,imu_valid,encoder_valid,path_valid,target_valid,link_alive,
    input wire rotation_clear,localization_lost,search_segment_done,search_timeout,
    input wire [15:0] front_mm,
    output reg active,force_stop,search_segment,locked,
    output reg [3:0] search_count,
    output reg [7:0] state,output reg [7:0] fault_code,
    output reg [9:0] speed_limit_mm_s
);
    localparam IDLE=0,RUN=1,SEARCH=2,FAULT=3,SETTLE=4,BLOCKED=5;
    reg [4:0] settle_ticks;
    function integer gcd(input integer a,input integer b);
        integer remainder;
        begin
            while(b!=0) begin remainder=a%b;a=b;b=remainder;end
            gcd=a;
        end
    endfunction
    localparam RANGE_MM=FRONT_SLOW_MM-FRONT_STOP_MM;
    localparam SCALE_GCD=gcd(100,RANGE_MM);
    localparam SCALE_NUM=100/SCALE_GCD,SCALE_DEN=RANGE_MM/SCALE_GCD;
    localparam SCALE_BITS=$clog2(RANGE_MM*SCALE_NUM+1);
    reg [SCALE_BITS-1:0] scaled_gap;
    reg [9:0] speed_cached;
    // Default 100/350 reduces to 2/7 in ten bits. Separate registers
    // keep division out of the distance-to-tracker path (two clock latency).
    // The hard stop below still reacts immediately, without waiting for it.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin scaled_gap<=0;speed_cached<=0;end
        else begin
            scaled_gap<=front_mm>FRONT_STOP_MM && front_mm<FRONT_SLOW_MM ?
                SCALE_BITS'(front_mm-FRONT_STOP_MM)*SCALE_BITS'(SCALE_NUM):{SCALE_BITS{1'b0}};
            speed_cached<=scaled_gap/SCALE_BITS'(SCALE_DEN);
        end
    always @* begin
        active=(state==RUN) && !localization_lost;
        search_segment=(state==SEARCH);
        locked=(state==FAULT);
        force_stop=((state!=RUN) && (state!=SEARCH)) || !link_alive || !lidar_valid || !imu_valid || !encoder_valid ||
            !geometry_verified || !map_valid || (state==RUN && ((ALLOW_REPLAN==0 && front_mm<=FRONT_STOP_MM) || localization_lost)) || (state==SEARCH && !rotation_clear);
        speed_limit_mm_s=10'd100;
        if(state==SEARCH) speed_limit_mm_s=SEARCH_SPEED_MM_S;
        else if(front_mm<=FRONT_STOP_MM) speed_limit_mm_s=0;
        else if(front_mm<FRONT_SLOW_MM) speed_limit_mm_s=speed_cached;
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin state<=IDLE;search_count<=0;fault_code<=0;settle_ticks<=0;end
        else begin
            if(cancel) begin state<=IDLE;search_count<=0;fault_code<=0;end
            else if(clear_fault && state==FAULT) begin state<=IDLE;search_count<=0;fault_code<=0;end
            else case(state)
                IDLE: if(start) begin
                    if(geometry_verified && map_valid && pose_valid && lidar_valid && imu_valid && encoder_valid &&
                       path_valid && target_valid && link_alive && (front_mm>FRONT_STOP_MM || (ALLOW_REPLAN!=0 && rotation_clear))) begin
                        state<=RUN;search_count<=0;fault_code<=0;
                    end else begin state<=FAULT;fault_code<=1;end
                end
                RUN: begin
                    if(!link_alive) begin state<=FAULT;fault_code<=2;end
                    else if(!geometry_verified || !map_valid || !imu_valid || !encoder_valid || !lidar_valid || !target_valid) begin state<=FAULT;fault_code<=3;end
                    else if((ALLOW_REPLAN==0 && front_mm<=FRONT_STOP_MM) || !path_valid) begin state<=FAULT;fault_code<=4;end
                    else if(localization_lost) begin
                        if(rotation_clear && lidar_valid && imu_valid) begin state<=SETTLE;settle_ticks<=0;end
                        else begin state<=FAULT;fault_code<=5;end
                    end
                end
                SEARCH: begin
                    if(!link_alive || !lidar_valid || !imu_valid || !encoder_valid || !rotation_clear || search_timeout) begin
                        state<=FAULT;fault_code<=6;
                    end else if(pose_valid && !localization_lost) begin state<=SETTLE;settle_ticks<=0;end
                    else if(search_segment_done) begin
                        if(search_count==11) begin state<=FAULT;fault_code<=7;end
                        else begin search_count<=search_count+1'b1;state<=SETTLE;settle_ticks<=0;end
                    end
                end
                SETTLE:begin
                    if(!link_alive || !lidar_valid || !imu_valid || !encoder_valid || !rotation_clear || !map_valid) begin state<=FAULT;fault_code<=6;end
                    else if(tick) begin
                        if(settle_ticks==19) state<=pose_valid && !localization_lost ? RUN:SEARCH;
                        else settle_ticks<=settle_ticks+1'b1;
                    end
                end
                BLOCKED:begin
                    if(!link_alive || !lidar_valid || !imu_valid || !encoder_valid || !geometry_verified || !map_valid) begin state<=FAULT;fault_code<=3;end
                    else if(start && path_valid && pose_valid && target_valid && rotation_clear) begin state<=RUN;fault_code<=0;end
                end
                default:;
            endcase
        end
endmodule
`default_nettype wire
