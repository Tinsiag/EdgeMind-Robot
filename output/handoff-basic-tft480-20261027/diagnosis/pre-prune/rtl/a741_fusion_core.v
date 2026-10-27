`timescale 1ns/1ps
`default_nettype none
// Sensor-fusion/map/safety island. The board shell supplies checked encoder
// distances and LD06 endpoint cells; autonomous motion stays denied until a
// verified footprint, localized pose and valid planned path are all present.
module a741_fusion_core(
    input wire clk,rst_n,tick,sample_valid,
    input wire signed [31:0] left_distance_mm,right_distance_mm,
    input wire signed [15:0] imu_yaw,
    input wire pose_set,input wire signed [31:0] set_pose_x_mm,set_pose_y_mm,input wire signed [15:0] set_pose_heading,
    output wire signed [31:0] pose_x_mm,pose_y_mm,
    output wire signed [15:0] pose_heading,
    output wire pose_valid,pose_overrun,
    input wire map_clear,
    input wire lidar_ray_start,input wire [6:0] ray_origin_x,ray_origin_y,ray_endpoint_x,ray_endpoint_y,
    output wire ray_busy,ray_done,ray_invalid,
    input wire host_map_write,input wire [6:0] host_write_x,host_write_y,input wire [1:0] host_write_value,
    output wire host_write_ready,
    input wire map_read,input wire [13:0] map_read_address,output wire [1:0] map_read_value,output wire map_read_done,
    output wire map_busy,map_valid,output wire [13:0] map_updates,
    input wire nav_start,nav_cancel,nav_clear_fault,
    input wire geometry_verified,planner_path_valid,target_valid,link_alive,
    input wire lidar_valid,imu_valid,encoder_valid,localized,rotation_clear,search_segment_done,
    input wire [15:0] front_mm,
    output wire nav_active,nav_stop,nav_search,nav_locked,
    output wire [3:0] nav_search_count,output wire [7:0] nav_state,nav_fault,
    output wire [9:0] nav_speed_limit_mm_s
);
    wire ray_update;wire [6:0] ray_x,ray_y;wire [1:0] ray_value;
    wire clear_busy;
    wire map_write=ray_update || (host_map_write && host_write_ready);
    wire [6:0] map_write_x=ray_update ? ray_x:host_write_x;
    wire [6:0] map_write_y=ray_update ? ray_y:host_write_y;
    wire [1:0] map_write_value=ray_update ? ray_value:host_write_value;
    assign host_write_ready=map_valid && !clear_busy && !ray_busy && !ray_update;
    assign map_busy=clear_busy || ray_busy;

    a741_pose_fusion pose(.clk(clk),.rst_n(rst_n),.tick(tick),.sample_valid(sample_valid),
        .pose_set(pose_set),.left_distance_mm(left_distance_mm),.right_distance_mm(right_distance_mm),.yaw(imu_yaw),
        .set_x_mm(set_pose_x_mm),.set_y_mm(set_pose_y_mm),.set_heading(set_pose_heading),
        .x_mm(pose_x_mm),.y_mm(pose_y_mm),.heading(pose_heading),.pose_valid(pose_valid),.overrun(pose_overrun));
    a741_ray_mapper ray(.clk(clk),.rst_n(rst_n),.start(lidar_ray_start && map_valid && !clear_busy),.cancel(map_clear),
        .origin_x(ray_origin_x),.origin_y(ray_origin_y),.endpoint_x(ray_endpoint_x),.endpoint_y(ray_endpoint_y),
        .busy(ray_busy),.update_valid(ray_update),.update_x(ray_x),.update_y(ray_y),.update_value(ray_value),
        .done(ray_done),.invalid(ray_invalid));
    a741_grid_map grid(.clk(clk),.rst_n(rst_n),.clear(map_clear),
        .write_valid(map_write),.write_x(map_write_x),.write_y(map_write_y),.write_value(map_write_value),
        .read_valid(map_read),.read_address(map_read_address),.read_value(map_read_value),.read_done(map_read_done),
        .clear_busy(clear_busy),.map_valid(map_valid),.write_count(map_updates));
    a741_nav_guard supervisor(.clk(clk),.rst_n(rst_n),.tick(tick),.start(nav_start),.cancel(nav_cancel),
        .clear_fault(nav_clear_fault),.geometry_verified(geometry_verified),.map_valid(map_valid),
        .pose_valid(pose_valid && localized),.lidar_valid(lidar_valid),.imu_valid(imu_valid),
        .encoder_valid(encoder_valid),.path_valid(planner_path_valid),.target_valid(target_valid),
        .link_alive(link_alive),.rotation_clear(rotation_clear),.localization_lost(!localized),.search_timeout(1'b0),
        .search_segment_done(search_segment_done),.front_mm(front_mm),.active(nav_active),
        .force_stop(nav_stop),.search_segment(nav_search),.locked(nav_locked),
        .search_count(nav_search_count),.state(nav_state),.fault_code(nav_fault),
        .speed_limit_mm_s(nav_speed_limit_mm_s));
endmodule
`default_nettype wire
