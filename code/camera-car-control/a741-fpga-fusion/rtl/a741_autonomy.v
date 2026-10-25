`timescale 1ns/1ps
`default_nettype none
// Board-domain integration. Motor ownership changes only through explicit commands.
module a741_autonomy #(parameter GEOMETRY_VERIFIED=0,RADIUS_MM=0,LIDAR_X=0,LIDAR_Y=0,
    LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1,TRACK_MM=234,CONFIG_CRC=0,FRONT_EXTENT=220,REAR_EXTENT=70,HALF_WIDTH=131)(
    input wire clk,rst_n,tick,ms_tick,imu_valid,lidar_valid,calibrated,armed,link_alive,
    input wire travel_tick,travel_valid,input wire signed [31:0] left_travel,right_travel,manual_left,manual_right,
    input wire signed [15:0] yaw,input wire [15:0] motor_faults,
    input wire lidar_point,input wire [15:0] lidar_angle,lidar_distance,input wire [7:0] lidar_confidence,
    input wire [15:0] lidar_front,lidar_left,lidar_right,
    input wire command,input wire [7:0] kind,input wire [255:0] payload,
    output reg reply_done,output reg [255:0] reply,
    output wire drive_enabled,force_stop,output wire signed [31:0] drive_left,drive_right,
    output wire sensor_stop,output wire [9:0] sensor_limit,
    output wire signed [31:0] pose_x,pose_y,output wire signed [15:0] pose_heading,
    output wire [7:0] nav_state,nav_fault,localization_quality,
    output wire [15:0] front_distance,output wire [31:0] map_revision
    ,output wire mission_busy,mission_arrived,mission_failed
);
    reg building,committed,pose_seeded,target_set,request_nav,nav_running,allow_generated_crc,preview_only;
    reg avoid_running,avoid_turning,avoid_turn_left;
    reg [3:0] navigation_phase;
    reg [15:0] replan_wait;reg [2:0] replans;
    reg [9:0] transfer_ms;
    wire map_command=command && (kind==8'h50 || kind==8'h51 || kind==8'h52) && !armed;
    reg [31:0] revision;
    assign map_revision=revision;
    reg clear_map,set_pose;reg signed [31:0] set_x,set_y;reg signed [15:0] set_yaw,goal_yaw;
    reg [6:0] goal_x,goal_y;
    wire pose_valid,pose_overrun;
    wire point_done,scan_end,project_overflow;
    wire signed [31:0] ex,ey,ox,oy,bx,by;wire [15:0] body_angle,range_mm;
    wire safe_scan,rotation_clear,nav_sensor_stop;
    wire [9:0] nav_sensor_limit;
    wire [15:0] nav_front_distance,rear_distance,min_distance,clearance;
    localparam [15:0] AVOID_STOP_MM=16'd450,AVOID_SLOW_MM=16'd900,
        AVOID_CLEAR_MM=16'd600,AVOID_SIDE_MM=16'd500;
    localparam signed [31:0] AVOID_CRUISE=32'sd120,AVOID_SLOW=32'sd60,
        AVOID_TURN=32'sd80;
    wire avoid_lidar_ok=lidar_valid && lidar_front!=16'hffff &&
        lidar_left!=16'hffff && lidar_right!=16'hffff;
    wire avoid_left_open=avoid_lidar_ok && lidar_left>=AVOID_SIDE_MM;
    wire avoid_right_open=avoid_lidar_ok && lidar_right>=AVOID_SIDE_MM;
    wire avoid_turn_blocked=avoid_turning &&
        ((avoid_turn_left && !avoid_left_open) ||
         (!avoid_turn_left && !avoid_right_open));
    wire avoid_sensor_stop=!avoid_lidar_ok || avoid_turn_blocked ||
        (!avoid_turning && lidar_front<=AVOID_STOP_MM &&
         !avoid_left_open && !avoid_right_open);
    wire signed [31:0] avoid_left_cmd=avoid_sensor_stop ? 32'sd0 :
        avoid_turning ? (avoid_turn_left ? -AVOID_TURN:AVOID_TURN) :
        (lidar_front<=AVOID_STOP_MM ? 32'sd0 :
         lidar_front<=AVOID_SLOW_MM ? AVOID_SLOW:AVOID_CRUISE);
    wire signed [31:0] avoid_right_cmd=avoid_sensor_stop ? 32'sd0 :
        avoid_turning ? (avoid_turn_left ? AVOID_TURN:-AVOID_TURN) :
        (lidar_front<=AVOID_STOP_MM ? 32'sd0 :
         lidar_front<=AVOID_SLOW_MM ? AVOID_SLOW:AVOID_CRUISE);
    wire [9:0] avoid_limit=!avoid_lidar_ok ? 10'd0 :
        avoid_turning ? 10'd80 :
        lidar_front<=AVOID_STOP_MM ? 10'd0 :
        lidar_front<=AVOID_SLOW_MM ? 10'd60:10'd120;
    // Assess the requested direction before the final pose/stop output gates.
    // Feeding gated drive outputs back here lengthens the safety feedback path
    // and loses direction information exactly when a stop gate becomes active.
    wire signed [31:0] safety_l=nav_running ? (guard_search ? -32'sd40:tracker_left):manual_left;
    wire signed [31:0] safety_r=nav_running ? (guard_search ? 32'sd40:tracker_right):manual_right;
    a741_pose_fusion #(.FRACTION_BITS(16)) pose(.clk(clk),.rst_n(rst_n),.tick(travel_tick && travel_valid),.sample_valid(imu_valid && calibrated),
        .pose_set(set_pose),.left_distance_mm(left_travel),.right_distance_mm(right_travel),.yaw(yaw),.set_heading(set_yaw),
        .set_x_mm(set_x),.set_y_mm(set_y),.x_mm(pose_x),.y_mm(pose_y),.heading(pose_heading),.pose_valid(pose_valid),.overrun(pose_overrun));
    a741_lidar_project projector(.clk(clk),.rst_n(rst_n),.valid(lidar_valid && pose_valid),.point_valid(lidar_point),
        .angle_cdeg(lidar_angle),.distance_mm(lidar_distance),.confidence(lidar_confidence),.heading(pose_heading),.pose_x(pose_x),.pose_y(pose_y),
        .offset_x(16'(LIDAR_X)),.offset_y(16'(LIDAR_Y)),.zero_cdeg(16'(LIDAR_ZERO)),.clockwise(LIDAR_CLOCKWISE!=0),
        .point_done(point_done),.scan_end(scan_end),.overflow(project_overflow),.endpoint_x(ex),.endpoint_y(ey),.origin_x(ox),.origin_y(oy),
        .body_x(bx),.body_y(by),.body_angle_cdeg(body_angle),.range_mm(range_mm));
    a741_lidar_safety #(.BODY_COORDINATES(1),.FRONT_EXTENT(FRONT_EXTENT),.REAR_EXTENT(REAR_EXTENT),.HALF_WIDTH(HALF_WIDTH)) safety(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.stream_valid(lidar_valid && !project_overflow),
        .point_valid(point_done),.scan_end(scan_end),.angle_cdeg(body_angle),.distance_mm(range_mm),.rotation_radius_mm(16'(RADIUS_MM)),
        .requested_left(safety_l),.requested_right(safety_r),.point_x(bx),.point_y(by),.stop(nav_sensor_stop),.rotation_clear(rotation_clear),.scan_valid(safe_scan),
        .front_mm(nav_front_distance),.rear_mm(rear_distance),.min_mm(min_distance),.clearance_mm(clearance),.speed_limit(nav_sensor_limit));

    wire ray_busy,ray_update,ray_done,ray_invalid;
    wire [6:0] ray_x,ray_y;wire [1:0] ray_value;
    wire [12:0] ex_grid=13'(ex+3200),ey_grid=13'(ey+3200),ox_grid=13'(ox+3200),oy_grid=13'(oy+3200);
    wire [7:0] cell_x=ex_grid/13'd50,cell_y=ey_grid/13'd50,origin_cx=ox_grid/13'd50,origin_cy=oy_grid/13'd50;
    wire bounded=ex>=-3200 && ex<3200 && ey>=-3200 && ey<3200 && ox>=-3200 && ox<3200 && oy>=-3200 && oy<3200;
    wire matcher_busy,match_read,match_done;wire [13:0] match_addr;wire [1:0] match_value;
    wire match_result,match_accepted,localized;wire signed [15:0] correction_x,correction_y,correction_yaw;
    wire inflate_busy,inflate_ready,inflate_read;wire [13:0] inflate_addr;
    reg inflate_start;wire plan_busy,plan_valid,plan_fail,plan_read;wire [13:0] plan_addr;wire plan_done;wire [1:0] plan_value;
    reg plan_start;wire plan_cell,plan_last;wire [6:0] plan_x,plan_y;wire [13:0] expanded;
    reg route_begin;
    wire tracker_ready,arrived,tracker_fault,tracker_blocked;wire [14:0] route_remaining;
    wire signed [31:0] tracker_left,tracker_right;
    wire guard_active,guard_stop,guard_search,guard_locked;wire [3:0] search_count;wire [9:0] nav_limit;
    reg nav_start,nav_cancel,nav_clear,search_done;reg [31:0] search_ms;reg signed [15:0] search_origin;
    reg was_search;
    wire signed [15:0] search_delta=pose_heading-search_origin;
    wire [9:0] limit=nav_limit<sensor_limit ? nav_limit:sensor_limit;
    reg [9:0] tracking_limit,tracking_turn_limit;
    // Tracking consumes a registered cap. Sensor stop and the final motor
    // inhibit remain independent and do not wait for this register.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin tracking_limit<=0;tracking_turn_limit<=0;end
        else begin
            tracking_limit<=limit;
            tracking_turn_limit<=rotation_clear ? sensor_limit:10'd0;
        end
    assign sensor_stop=avoid_running ? avoid_sensor_stop:nav_sensor_stop;
    assign sensor_limit=avoid_running ? avoid_limit:nav_sensor_limit;
    assign front_distance=avoid_running ? lidar_front:nav_front_distance;
    assign drive_enabled=avoid_running || nav_running || (request_nav && !preview_only);
    assign drive_left=avoid_running ? avoid_left_cmd:
        request_nav ? 32'sd0:guard_search && !guard_stop ? -32'sd40:
        guard_active && !guard_stop ? tracker_left:32'sd0;
    assign drive_right=avoid_running ? avoid_right_cmd:
        request_nav ? 32'sd0:guard_search && !guard_stop ? 32'sd40:
        guard_active && !guard_stop ? tracker_right:32'sd0;
    assign force_stop=(avoid_running && (!armed || !link_alive || motor_faults!=0)) ||
        (nav_running && (guard_locked || tracker_fault || !safe_scan || replans==7));
    assign mission_busy=avoid_running || nav_running || request_nav;
    assign mission_arrived=arrived && !request_nav;
    assign mission_failed=guard_locked || tracker_fault || plan_fail || replans==7;

    reg host_write,host_read;reg [13:0] host_address;reg [1:0] host_value;
    wire map_ready,map_clear_busy,map_read_done;wire [1:0] map_read_value;wire [13:0] map_updates;
    wire map_read=inflate_busy ? inflate_read:matcher_busy ? match_read:host_read;
    wire [13:0] map_addr=inflate_busy ? inflate_addr:matcher_busy ? match_addr:host_address;
    wire obstacle_update=point_done && nav_running && bounded && !matcher_busy && !inflate_busy && !plan_busy && op_state==0;
    wire map_write=ray_update || host_write || obstacle_update;
    wire [13:0] map_waddr=ray_update ? {ray_y,ray_x}:obstacle_update ? {cell_y[6:0],cell_x[6:0]}:host_address;
    a741_grid_map grid(.clk(clk),.rst_n(rst_n),.clear(clear_map),.write_valid(map_write),.write_x(map_waddr[6:0]),.write_y(map_waddr[13:7]),
        .write_value(ray_update ? ray_value:obstacle_update ? 2'b10:host_value),.read_valid(map_read),.read_address(map_addr),.read_value(map_read_value),.read_done(map_read_done),
        .clear_busy(map_clear_busy),.map_valid(map_ready),.write_count(map_updates));
    a741_ray_mapper rasterizer(.clk(clk),.rst_n(rst_n),.start(point_done && building && bounded && !matcher_busy && !inflate_busy),
        .cancel(clear_map || !building),.origin_x(origin_cx[6:0]),.origin_y(origin_cy[6:0]),.endpoint_x(cell_x[6:0]),.endpoint_y(cell_y[6:0]),
        .busy(ray_busy),.update_valid(ray_update),.update_x(ray_x),.update_y(ray_y),.update_value(ray_value),.done(ray_done),.invalid(ray_invalid));
    a741_scan_match matcher(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.enable(committed && pose_seeded && !inflate_busy && !plan_busy && op_state==0 && transfer_ms==0 && !map_command && (!request_nav || navigation_phase==6)),
        .cancel(clear_map || !lidar_valid || !imu_valid),.point_valid(point_done),.scan_end(scan_end),.endpoint_x(ex),.endpoint_y(ey),.pose_x(pose_x),.pose_y(pose_y),
        .busy(matcher_busy),.map_read(match_read),.map_address(match_addr),.map_done(map_read_done && matcher_busy),.map_value(map_read_value),
        .result_valid(match_result),.accepted(match_accepted),.localized(localized),.correction_x(correction_x),.correction_y(correction_y),
        .correction_yaw(correction_yaw),.quality(localization_quality));
    a741_inflate inflate(.clk(clk),.rst_n(rst_n),.start(inflate_start),.cancel(nav_cancel || clear_map),.radius_cells(5'((RADIUS_MM+149)/50)),
        .busy(inflate_busy),.ready(inflate_ready),.raw_read(inflate_read),.raw_address(inflate_addr),.raw_done(map_read_done && inflate_busy),.raw_value(map_read_value),
        .query(plan_read),.query_address(plan_addr),.query_done(plan_done),.query_value(plan_value));
    wire [12:0] pose_grid_x=13'(pose_x+3200),pose_grid_y=13'(pose_y+3200);
    wire [7:0] pcx=pose_grid_x/13'd50,pcy=pose_grid_y/13'd50;
    wire pose_in_map=pose_x>=-3200 && pose_x<3200 && pose_y>=-3200 && pose_y<3200;
    a741_path_planner planner(.clk(clk),.rst_n(rst_n),.start(plan_start),.cancel(nav_cancel || clear_map),.map_valid(inflate_ready),
        .start_x(pcx[6:0]),.start_y(pcy[6:0]),.goal_x(goal_x),.goal_y(goal_y),.map_read_valid(plan_read),.map_read_address(plan_addr),
        .map_read_value(plan_value),.map_read_done(plan_done),.busy(plan_busy),.path_valid(plan_valid),.no_path(plan_fail),
        .path_cell_valid(plan_cell),.path_cell_x(plan_x),.path_cell_y(plan_y),.path_cell_last(plan_last),.expanded_nodes(expanded));
    a741_path_tracker #(.TRACK_MM(TRACK_MM),.DIRECTIONAL_LIMITS(1)) tracker(.clk(clk),.rst_n(rst_n),.tick(tick),.load_begin(route_begin),.load_valid(plan_cell),.load_last(plan_last),
        .load_x(plan_x),.load_y(plan_y),.enable(nav_running && guard_active && !sensor_stop),.cancel(nav_cancel),.speed_limit(tracking_limit),
        .turn_limit(tracking_turn_limit),
        .pose_x(pose_x),.pose_y(pose_y),.heading(pose_heading),.goal_heading(goal_yaw),.left_target(tracker_left),.right_target(tracker_right),
        .route_ready(tracker_ready),.arrived(arrived),.fault(tracker_fault),.blocked(tracker_blocked),.remaining(route_remaining));
    a741_nav_guard #(.ALLOW_REPLAN(1)) guard(.clk(clk),.rst_n(rst_n),.tick(tick),.start(nav_start),.cancel(nav_cancel),.clear_fault(nav_clear),
        .geometry_verified(GEOMETRY_VERIFIED!=0),.map_valid(committed && pose_in_map),.pose_valid(pose_valid && localized),.lidar_valid(safe_scan),
        .imu_valid(imu_valid && calibrated),.encoder_valid(motor_faults==0),.path_valid(plan_valid && tracker_ready),.target_valid(target_set),.link_alive(link_alive),
        .rotation_clear(rotation_clear),.localization_lost(!localized),.search_segment_done(search_done),.search_timeout(search_ms>=6000),.front_mm(front_distance),
        .active(guard_active),.force_stop(guard_stop),.search_segment(guard_search),.locked(guard_locked),.search_count(search_count),
        .state(nav_state),.fault_code(nav_fault),.speed_limit_mm_s(nav_limit));

    reg [4:0] op_state,byte_index,cell_index,byte_count;
    reg [7:0] op,packed_byte;reg [11:0] packed_address;
    reg [191:0] data_bytes;
    reg [31:0] crc,expected_crc;
    reg [11:0] crc_address;
    reg [15:0] age;
    function [31:0] crc_byte(input [31:0] old,input [7:0] data);
        reg [31:0] v;integer n;begin v=old^data;for(n=0;n<8;n=n+1) v=v[0] ? (v>>1)^32'hedb88320:v>>1;crc_byte=v;end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            building<=0;committed<=0;pose_seeded<=0;target_set<=0;request_nav<=0;nav_running<=0;avoid_running<=0;avoid_turning<=0;avoid_turn_left<=0;revision<=0;navigation_phase<=0;allow_generated_crc<=0;preview_only<=0;
            clear_map<=0;set_pose<=0;set_x<=0;set_y<=0;set_yaw<=0;goal_x<=0;goal_y<=0;goal_yaw<=0;
            transfer_ms<=0;replan_wait<=0;replans<=0;
            reply_done<=0;reply<=0;host_write<=0;host_read<=0;host_address<=0;host_value<=0;
            inflate_start<=0;plan_start<=0;route_begin<=0;nav_start<=0;nav_cancel<=0;nav_clear<=0;
            search_done<=0;search_ms<=0;search_origin<=0;was_search<=0;op_state<=0;op<=0;
            byte_index<=0;cell_index<=0;byte_count<=0;packed_byte<=0;packed_address<=0;data_bytes<=0;
            crc<=32'hffffffff;expected_crc<=0;crc_address<=0;age<=0;
        end else begin
            clear_map<=0;set_pose<=0;reply_done<=0;host_write<=0;host_read<=0;inflate_start<=0;plan_start<=0;
            route_begin<=0;nav_start<=0;nav_cancel<=0;nav_clear<=0;search_done<=0;was_search<=guard_search;
            if(ms_tick && transfer_ms!=0) transfer_ms<=transfer_ms-1'b1;
            if(map_command) transfer_ms<=1000;
            if(!calibrated) pose_seeded<=0;
            // A zero correction must preserve Q16 odometry fractions. Repeated
            // integer-mm pose resets otherwise discard sub-mm motion each scan.
            if(match_result && match_accepted && op_state==0 &&
                (correction_x!=0 || correction_y!=0 || correction_yaw!=0)) begin
                set_x<=pose_x+correction_x;set_y<=pose_y+correction_y;set_yaw<=pose_heading+correction_yaw;set_pose<=1;
            end
            if(guard_search && !was_search) begin search_origin<=pose_heading;search_ms<=0;end
            if(ms_tick && guard_search) begin
                search_ms<=search_ms+1'b1;
                if(search_delta>=5461) search_done<=1;
            end
            if(ms_tick && avoid_running && avoid_lidar_ok) begin
                if(avoid_turning) begin
                    if(lidar_front>=AVOID_CLEAR_MM) avoid_turning<=0;
                end else if(lidar_front<=AVOID_STOP_MM &&
                             (avoid_left_open || avoid_right_open)) begin
                    avoid_turning<=1;
                    avoid_turn_left<=avoid_left_open && (!avoid_right_open ||
                        lidar_left>=lidar_right);
                end
            end
            if(nav_running && !request_nav && guard_active && safe_scan &&
                ((sensor_stop && (drive_left!=0 || drive_right!=0)) || tracker_blocked) && replans<7) begin
                request_nav<=1;navigation_phase<=7;preview_only<=0;replan_wait<=0;replans<=replans+1'b1;
            end
            if(request_nav) case(navigation_phase)
                1:begin inflate_start<=1;navigation_phase<=2;end
                2:if(inflate_busy) navigation_phase<=3;
                3:if(inflate_ready) begin plan_start<=1;route_begin<=1;navigation_phase<=4;end
                4:if(plan_busy) navigation_phase<=5;
                5:if(plan_valid && tracker_ready) begin
                    if(preview_only) begin request_nav<=0;navigation_phase<=0;end
                    else navigation_phase<=6;
                end
                6:if(localized && safe_scan && rotation_clear) begin nav_start<=1;nav_running<=1;request_nav<=0;navigation_phase<=0;end
                7:if(ms_tick) begin
                    if(replan_wait==299) begin nav_cancel<=1;navigation_phase<=1;end
                    else replan_wait<=replan_wait+1'b1;
                end
                default:;
            endcase
            // A previous leg's sticky arrived flag clears on route_begin.
            // It must not cancel the next leg in the cycle before that clear.
            if(avoid_running && (!link_alive || motor_faults!=0 || !armed)) begin avoid_running<=0;avoid_turning<=0;end
              if((plan_fail && navigation_phase==5) || guard_locked || (arrived && nav_running) || tracker_fault || !link_alive || motor_faults!=0 || (nav_running && !armed)) begin
                request_nav<=0;nav_running<=0;navigation_phase<=0;
            end
            if(command && (kind==3 || kind==4 || kind==8'h56 || (kind==8'h59 && payload[7:0]==0))) begin nav_cancel<=1;nav_running<=0;request_nav<=0;end
            if(command && kind==8'h21) nav_clear<=1;
            if(command && kind>=8'h50 && kind<=8'h59 && op_state==0) begin
                reply<=0;reply[7:0]<=0;reply_done<=1;
                case(kind)
                    8'h50:if(armed || nav_running || plan_busy || inflate_busy || payload[7:0]>1) reply[7:0]<=2;
                        else begin
                            clear_map<=1;building<=payload[7:0]==1;committed<=0;revision<=revision+1'b1;
                            nav_cancel<=1;pose_seeded<=1;set_x<=0;set_y<=0;set_yaw<=0;set_pose<=1;
                        end
                    8'h51:if(armed || building || ray_busy || inflate_busy || plan_busy || !map_ready ||
                        payload[31:24]==0 || payload[31:24]>24 || payload[23:8]+payload[31:24]>4096 || payload[7:0]>1) reply[7:0]<=2;
                        else begin
                            reply_done<=0;op<=payload[7:0];packed_address<=payload[19:8];byte_count<=payload[31:24];
                            byte_index<=0;cell_index<=0;data_bytes<=payload[223:32];op_state<=1;
                        end
                    8'h52:if(armed || ray_busy || plan_busy || inflate_busy || !map_ready) reply[7:0]<=2;
                        else begin
                            reply_done<=0;building<=0;allow_generated_crc<=building;expected_crc<=payload[31:0];crc<=32'hffffffff;
                            crc_address<=0;cell_index<=0;packed_byte<=0;op_state<=5;committed<=0;
                        end
                    8'h53:if(armed || request_nav || matcher_busy || !imu_valid || !calibrated) reply[7:0]<=2;
                        else if($signed(payload[31:0])< -3100 || $signed(payload[31:0])>3100 || $signed(payload[63:32])< -3100 || $signed(payload[63:32])>3100) reply[7:0]<=3;
                        else begin set_x<=payload[31:0];set_y<=payload[63:32];set_yaw<=payload[79:64];set_pose<=1;pose_seeded<=1;end
                    8'h54:if(nav_running || request_nav || payload[7:0]>127 || payload[15:8]>127) reply[7:0]<=2;
                        else begin
                            goal_x<=payload[6:0];goal_y<=payload[14:8];goal_yaw<=payload[31:16];target_set<=1;
                            if(committed && pose_seeded && !armed) begin request_nav<=1;navigation_phase<=1;preview_only<=1;nav_cancel<=1;route_begin<=1;end
                        end
                    8'h55:if(GEOMETRY_VERIFIED==0 || RADIUS_MM==0 || request_nav || nav_running || manual_left!=0 || manual_right!=0 || !pose_in_map || !armed || !localized || !safe_scan || !rotation_clear ||
                        !target_set || !pose_seeded || !committed || !link_alive || motor_faults!=0) reply[7:0]<=1;
                        else begin request_nav<=1;navigation_phase<=1;preview_only<=0;nav_cancel<=1;route_begin<=1;replans<=0;end
                    8'h56:begin nav_cancel<=1;request_nav<=0;nav_running<=0;end
                    8'h57:begin
                        reply[7:0]<=0;reply[15:8]<=request_nav ? 4:nav_state;reply[23:16]<=plan_fail ? 8:nav_fault;
                        reply[31:24]<={GEOMETRY_VERIFIED!=0,request_nav,building,committed,localized,pose_valid,safe_scan,nav_running};
                        reply[63:32]<=pose_x;reply[95:64]<=pose_y;reply[111:96]<=pose_heading;
                        reply[127:112]<=front_distance;reply[159:128]<=revision;reply[167:160]<=localization_quality;
                        reply[191:176]<=route_remaining;reply[207:192]<=expanded;
                        reply[239:208]<=CONFIG_CRC;
                    end
                      8'h59:if(payload[7:0]>1 ||
                              (payload[7:0]==1 && (!armed || nav_running || request_nav)))
                              reply[7:0]<=1;
                          else begin
                              avoid_running<=payload[7:0]==1;
                              avoid_turning<=0;
                              avoid_turn_left<=0;
                          end
                      default:;
                endcase
            end
            case(op_state)
                1:begin
                    host_address<={packed_address,cell_index[1:0]};
                    if(op==1) begin host_value<=data_bytes[byte_index*8+cell_index*2+:2];host_write<=1;op_state<=3;committed<=0;end
                    else begin host_read<=1;op_state<=2;end
                end
                2:if(map_read_done) begin reply[32+byte_index*8+cell_index*2+:2]<=map_read_value;op_state<=3;end
                3:if(cell_index==3) begin
                    cell_index<=0;packed_address<=packed_address+1'b1;
                    if(byte_index+1==byte_count) begin reply_done<=1;op_state<=0;end
                    else begin byte_index<=byte_index+1'b1;op_state<=1;end
                end else begin cell_index<=cell_index+1'b1;op_state<=1;end
                5:begin host_address<={crc_address,cell_index[1:0]};host_read<=1;op_state<=6;end
                6:if(map_read_done) begin packed_byte[cell_index*2+:2]<=map_read_value;op_state<=7;end
                7:if(cell_index==3) begin crc<=crc_byte(crc,packed_byte);cell_index<=0;op_state<=8;end
                    else begin cell_index<=cell_index+1'b1;op_state<=5;end
                8:if(crc_address==4095) begin
                    reply_done<=1;reply[63:32]<=~crc;
                    if((expected_crc==0 && allow_generated_crc) || expected_crc==~crc) begin committed<=1;revision<=revision+1'b1;reply[7:0]<=0;end
                    else begin reply[7:0]<=4;committed<=0;end
                    op_state<=0;
                end else begin crc_address<=crc_address+1'b1;op_state<=5;end
                default:;
            endcase
        end
endmodule
`default_nettype wire
