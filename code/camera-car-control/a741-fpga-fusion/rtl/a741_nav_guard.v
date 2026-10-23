`timescale 1ns/1ps
`default_nettype none
// Fail-closed navigation authorization and bounded yaw-search recovery.
module a741_nav_guard #(parameter FRONT_STOP_MM=250,FRONT_SLOW_MM=600,SEARCH_SPEED_MM_S=40)(
    input wire clk,rst_n,tick,start,cancel,clear_fault,
    input wire geometry_verified,map_valid,pose_valid,lidar_valid,imu_valid,encoder_valid,path_valid,target_valid,link_alive,
    input wire rotation_clear,localization_lost,search_segment_done,search_timeout,
    input wire [15:0] front_mm,
    output reg active,force_stop,search_segment,locked,
    output reg [3:0] search_count,
    output reg [7:0] state,output reg [7:0] fault_code,
    output reg [9:0] speed_limit_mm_s
);
    localparam IDLE=0,RUN=1,SEARCH=2,FAULT=3,SETTLE=4;
    reg [4:0] settle_ticks;
    always @* begin
        active=(state==RUN) && !localization_lost;
        search_segment=(state==SEARCH);
        locked=(state==FAULT);
        force_stop=((state!=RUN) && (state!=SEARCH)) || !link_alive || !lidar_valid || !imu_valid || !encoder_valid ||
            !geometry_verified || !map_valid || (state==RUN && (front_mm<=FRONT_STOP_MM || localization_lost)) || (state==SEARCH && !rotation_clear);
        speed_limit_mm_s=10'd100;
        if(state==SEARCH) speed_limit_mm_s=SEARCH_SPEED_MM_S;
        else if(front_mm<=FRONT_STOP_MM) speed_limit_mm_s=0;
        else if(front_mm<FRONT_SLOW_MM) speed_limit_mm_s=
            ((front_mm-FRONT_STOP_MM)*100)/(FRONT_SLOW_MM-FRONT_STOP_MM);
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin state<=IDLE;search_count<=0;fault_code<=0;settle_ticks<=0;end
        else begin
            if(cancel) begin state<=IDLE;search_count<=0;fault_code<=0;end
            else if(clear_fault && state==FAULT) begin state<=IDLE;search_count<=0;fault_code<=0;end
            else case(state)
                IDLE: if(start) begin
                    if(geometry_verified && map_valid && pose_valid && lidar_valid && imu_valid && encoder_valid &&
                       path_valid && target_valid && link_alive && front_mm>FRONT_STOP_MM) begin
                        state<=RUN;search_count<=0;fault_code<=0;
                    end else begin state<=FAULT;fault_code<=1;end
                end
                RUN: begin
                    if(!link_alive) begin state<=FAULT;fault_code<=2;end
                    else if(!geometry_verified || !map_valid || !imu_valid || !encoder_valid || !lidar_valid || !target_valid) begin state<=FAULT;fault_code<=3;end
                    else if(front_mm<=FRONT_STOP_MM || !path_valid) begin state<=FAULT;fault_code<=4;end
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
                default:;
            endcase
        end
endmodule
`default_nettype wire
