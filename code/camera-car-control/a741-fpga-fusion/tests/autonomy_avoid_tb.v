`timescale 1ns/1ps
// Minimal sensor-only cruise test: no map, pose, planner, or board I/O.
module autonomy_avoid_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0;
    integer cycles=0;
    wire ms_tick=(cycles%10)==9;
    wire tick=(cycles%100)==99;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;

    reg imu_valid=1, lidar_valid=1, calibrated=1, armed=1, link_alive=1;
    reg travel_tick=0, travel_valid=1;
    reg signed [31:0] left_travel=0, right_travel=0;
    reg signed [31:0] manual_left=0, manual_right=0;
    reg signed [15:0] yaw=0;
    reg [15:0] motor_faults=0;
    reg lidar_point=0;
    reg [15:0] lidar_angle=0, lidar_distance=1000;
    reg [7:0] lidar_confidence=100;
    reg command=0;
    reg [7:0] kind=0;
    reg [255:0] payload=0;
    reg [15:0] lidar_front=16'd1500, lidar_left=16'd1500,
               lidar_right=16'd1500;

    wire reply_done;
    wire [255:0] reply;
    wire drive_enabled,force_stop,sensor_stop;
    wire signed [31:0] drive_left,drive_right,pose_x,pose_y;
    wire [9:0] sensor_limit;
    wire signed [15:0] pose_heading;
    wire [7:0] nav_state,nav_fault,localization_quality;
    wire [15:0] front_distance;
    wire [31:0] map_revision;
    wire mission_busy,mission_arrived,mission_failed;

    a741_autonomy dut(
        .clk(clk),.rst_n(rst_n),.tick(tick),.ms_tick(ms_tick),
        .imu_valid(imu_valid),.lidar_valid(lidar_valid),.calibrated(calibrated),
        .armed(armed),.link_alive(link_alive),.travel_tick(travel_tick),
        .travel_valid(travel_valid),.left_travel(left_travel),
        .right_travel(right_travel),.manual_left(manual_left),
        .manual_right(manual_right),.yaw(yaw),.motor_faults(motor_faults),
        .lidar_point(lidar_point),.lidar_angle(lidar_angle),
        .lidar_distance(lidar_distance),.lidar_confidence(lidar_confidence),
        .lidar_front(lidar_front),.lidar_left(lidar_left),
        .lidar_right(lidar_right),.command(command),.kind(kind),
        .payload(payload),.reply_done(reply_done),.reply(reply),
        .drive_enabled(drive_enabled),.force_stop(force_stop),
        .drive_left(drive_left),.drive_right(drive_right),
        .sensor_stop(sensor_stop),.sensor_limit(sensor_limit),
        .pose_x(pose_x),.pose_y(pose_y),.pose_heading(pose_heading),
        .nav_state(nav_state),.nav_fault(nav_fault),
        .localization_quality(localization_quality),
        .front_distance(front_distance),.map_revision(map_revision),
        .mission_busy(mission_busy),.mission_arrived(mission_arrived),
        .mission_failed(mission_failed)
    );

    task send_cmd;
        input [7:0] k;
        input [255:0] p;
        integer wait_cycles;
        begin
            @(negedge clk); kind=k; payload=p; command=1;
            @(negedge clk); command=0;
            wait_cycles=0;
            while(!reply_done && wait_cycles<100) begin
                @(negedge clk); wait_cycles=wait_cycles+1;
            end
            if(!reply_done || reply[7:0]!=0)
                $fatal(1,"command %h failed reply=%h",k,reply[7:0]);
        end
    endtask

    task wait_ms;
        integer n;
        begin for(n=0;n<24;n=n+1) @(negedge clk); end
    endtask

    initial begin
        #30; rst_n=1;
        send_cmd(8'h59,256'd1);
        if(!drive_enabled || drive_left!==32'sd120 || drive_right!==32'sd120)
            $fatal(1,"open path did not cruise: enable=%0d L=%0d R=%0d",
                drive_enabled,drive_left,drive_right);
        if(sensor_limit!==10'd120) $fatal(1,"cruise limit=%0d",sensor_limit);

        lidar_front=16'd700;
        #1;
        if(drive_left!==32'sd60 || drive_right!==32'sd60 ||
           sensor_limit!==10'd60) $fatal(1,"slow response L=%0d R=%0d cap=%0d",
                drive_left,drive_right,sensor_limit);

        lidar_front=16'd300; lidar_left=16'd800; lidar_right=16'd550;
        wait_ms();
        if(!dut.avoid_turning || !dut.avoid_turn_left ||
           drive_left!==-32'sd80 || drive_right!==32'sd80)
            $fatal(1,"left opening was not selected: turning=%0d left=%0d cmd=%0d/%0d",
                dut.avoid_turning,dut.avoid_turn_left,drive_left,drive_right);

        lidar_front=16'd700;
        wait_ms();
        if(dut.avoid_turning || drive_left!==32'sd60 || drive_right!==32'sd60)
            $fatal(1,"turn did not release: turning=%0d cmd=%0d/%0d",
                dut.avoid_turning,drive_left,drive_right);

        lidar_front=16'd300; lidar_left=16'd520; lidar_right=16'd800;
        wait_ms();
        if(!dut.avoid_turning || dut.avoid_turn_left ||
           drive_left!==32'sd80 || drive_right!==-32'sd80)
            $fatal(1,"right opening was not selected: turning=%0d left=%0d cmd=%0d/%0d",
                dut.avoid_turning,dut.avoid_turn_left,drive_left,drive_right);

        lidar_front=16'd300; lidar_left=16'd400; lidar_right=16'd400;
        wait_ms();
        if(!sensor_stop || drive_left!==0 || drive_right!==0)
            $fatal(1,"blocked corridor did not stop: stop=%0d cmd=%0d/%0d",
                sensor_stop,drive_left,drive_right);

        lidar_valid=0; #1;
        if(!sensor_stop || drive_left!==0 || drive_right!==0)
            $fatal(1,"invalid lidar did not stop");
        lidar_valid=1; lidar_front=16'd1500; lidar_left=16'd1500; lidar_right=16'd1500;
        wait_ms();
        if(dut.avoid_turning || drive_left!==32'sd120 || drive_right!==32'sd120)
            $fatal(1,"valid lidar did not release turn: turning=%0d cmd=%0d/%0d",
                dut.avoid_turning,drive_left,drive_right);
        send_cmd(8'h59,256'd0);
        if(drive_enabled || drive_left!==0 || drive_right!==0 || dut.avoid_running)
            $fatal(1,"stop command retained autonomous ownership");
        $display("PASS autonomous avoidance cruise, slow, wider-side turns, block and invalid-lidar stop");
        $finish;
    end

    initial begin
        #200000;
        $fatal(1,"avoidance watchdog state=%0d turn=%0d cmd=%0d/%0d",
            dut.avoid_running,dut.avoid_turning,drive_left,drive_right);
    end
endmodule
