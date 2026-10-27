`timescale 1ns/1ps
module fusion_core_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,sample_valid=1;
    reg signed [31:0] left_distance=0,right_distance=0;
    reg signed [15:0] imu_yaw=0;
    reg pose_set=0;reg signed [31:0] set_x=100,set_y=-50;reg signed [15:0] set_heading=0;
    reg map_clear=0,ray_start=0;reg [6:0] ray_ox=64,ray_oy=64,ray_ex=66,ray_ey=64;
    reg host_write=0;reg [6:0] host_x=3,host_y=2;reg [1:0] host_value=2'b10;
    wire host_ready;reg map_read=0;reg [13:0] read_address=0;wire [1:0] read_value;wire read_done;
    wire signed [31:0] pose_x,pose_y;wire signed [15:0] pose_heading;wire pose_valid,pose_overrun;
    wire ray_busy,ray_done,ray_invalid,map_busy,map_valid;wire [13:0] map_updates;
    reg nav_start=0,nav_cancel=0,nav_clear_fault=0;
    reg geometry_verified=0,path_valid=0,target_valid=1,link_alive=1;
    reg lidar_valid=1,imu_valid=1,encoder_valid=1,localized=1,rotation_clear=1,search_done=0;
    reg [15:0] front_mm=1000;
    wire nav_active,nav_stop,nav_search,nav_locked;wire [3:0] search_count;wire [7:0] nav_state,nav_fault;wire [9:0] nav_speed;
    a741_fusion_core dut(.clk(clk),.rst_n(rst_n),.tick(tick),.sample_valid(sample_valid),
        .left_distance_mm(left_distance),.right_distance_mm(right_distance),.imu_yaw(imu_yaw),
        .pose_set(pose_set),.set_pose_x_mm(set_x),.set_pose_y_mm(set_y),.set_pose_heading(set_heading),
        .pose_x_mm(pose_x),.pose_y_mm(pose_y),.pose_heading(pose_heading),.pose_valid(pose_valid),.pose_overrun(pose_overrun),
        .map_clear(map_clear),.lidar_ray_start(ray_start),.ray_origin_x(ray_ox),.ray_origin_y(ray_oy),
        .ray_endpoint_x(ray_ex),.ray_endpoint_y(ray_ey),.ray_busy(ray_busy),.ray_done(ray_done),.ray_invalid(ray_invalid),
        .host_map_write(host_write),.host_write_x(host_x),.host_write_y(host_y),.host_write_value(host_value),.host_write_ready(host_ready),
        .map_read(map_read),.map_read_address(read_address),.map_read_value(read_value),.map_read_done(read_done),
        .map_busy(map_busy),.map_valid(map_valid),.map_updates(map_updates),
        .nav_start(nav_start),.nav_cancel(nav_cancel),.nav_clear_fault(nav_clear_fault),
        .geometry_verified(geometry_verified),.planner_path_valid(path_valid),.target_valid(target_valid),.link_alive(link_alive),
        .lidar_valid(lidar_valid),.imu_valid(imu_valid),.encoder_valid(encoder_valid),.localized(localized),
        .rotation_clear(rotation_clear),.search_segment_done(search_done),.front_mm(front_mm),
        .nav_active(nav_active),.nav_stop(nav_stop),.nav_search(nav_search),.nav_locked(nav_locked),
        .nav_search_count(search_count),.nav_state(nav_state),.nav_fault(nav_fault),.nav_speed_limit_mm_s(nav_speed));
    task read_cell(input [13:0] address,input [1:0] expected);
        begin @(negedge clk);read_address=address;map_read=1;@(negedge clk);#1;map_read=0;
            if(!read_done || read_value!==expected) $fatal(1,"integrated map cell %0d=%0d expected %0d",address,read_value,expected);end
    endtask
    integer i;
    initial begin
        #30;rst_n=1;@(negedge clk);map_clear=1;@(negedge clk);map_clear=0;
        for(i=0;i<16385;i=i+1) @(negedge clk);
        if(!map_valid) $fatal(1,"integrated map did not initialize");
        @(negedge clk);host_write=1;@(negedge clk);host_write=0;
        read_cell(14'd259,2'b10);
        @(negedge clk);pose_set=1;@(negedge clk);pose_set=0;
        if(!pose_valid || pose_x!=100 || pose_y!=-50) $fatal(1,"host pose initialization");
        left_distance=100;right_distance=100;@(negedge clk);tick=1;@(negedge clk);tick=0;repeat(20) @(negedge clk);
        if(pose_x<198 || pose_x>202 || pose_y!=-50) $fatal(1,"integrated odometry");
        @(negedge clk);ray_start=1;@(negedge clk);ray_start=0;wait(ray_done);@(negedge clk);#1;
        read_cell(14'd8256,2'b01);read_cell(14'd8258,2'b10);
        @(negedge clk);nav_start=1;@(negedge clk);nav_start=0;
        if(!nav_locked || nav_active || !nav_stop) $fatal(1,"planner/geometry interlock");
        $display("PASS fused pose, map import/read, lidar ray and navigation interlock");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
