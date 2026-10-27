`timescale 1ns/1ps
// Minimal sensor-only cruise test: no map, pose, planner, or board I/O.
module avoidance_lite_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0;
    integer cycles=0;
    wire ms_tick=(cycles%10)==9;
    wire tick=(cycles%100)==99;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;

    reg imu_valid=1, lidar_valid=1, calibrated=1, armed=1, link_alive=1;
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
    wire signed [31:0] drive_left,drive_right;
    wire [9:0] sensor_limit;
    wire [7:0] nav_state,nav_fault;
    wire [15:0] front_distance;

    a741_avoidance #(.GEOMETRY_VERIFIED(1)) dut(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.armed(armed),.link_alive(link_alive),
        .motor_faults(motor_faults),.imu_valid(imu_valid),.tilt_valid(1'b1),.roll(16'sd0),.pitch(16'sd0),.manual_left(manual_left),.manual_right(manual_right),.yaw(yaw),
        .lidar_valid(lidar_valid),.lidar_front(lidar_front),.lidar_left(lidar_left),.lidar_right(lidar_right),
        .manual_stop(1'b0),.manual_limit(10'd400),.manual_scan_valid(1'b1),
        .supervisor_alive(1'b1),.supervisor_fault(1'b0),.supervisor_uptime(32'd0),
        .command(command),.kind(kind),.payload(payload),.reply_done(reply_done),.reply(reply),
        .drive_enabled(drive_enabled),.force_stop(force_stop),.drive_left(drive_left),.drive_right(drive_right),
        .sensor_stop(sensor_stop),.sensor_limit(sensor_limit),.state(nav_state),.fault(nav_fault),.front_distance(front_distance));

    task send_cmd(input [7:0] k,input [255:0] p,input [7:0] expected=0);
        integer wait_cycles;
        begin
            @(negedge clk); kind=k; payload=p; command=1;
            @(negedge clk); command=0;
            wait_cycles=0;
            while(!reply_done && wait_cycles<100) begin
                @(negedge clk); wait_cycles=wait_cycles+1;
            end
            if(!reply_done || reply[7:0]!=expected)
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

        send_cmd(8'h59,256'd1,1);
        if(!dut.avoid_turning || !dut.avoid_turn_left) $fatal(1,"duplicate start reset turn state");
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
        lidar_front=901;send_cmd(8'h59,256'd1);
        if(drive_left!=120) $fatal(1,"901mm cruise boundary");
        lidar_front=900;#1;if(drive_left!=60) $fatal(1,"900mm slow boundary");
        lidar_front=451;#1;if(drive_left!=60) $fatal(1,"451mm slow boundary");
        lidar_front=450;lidar_left=500;lidar_right=499;wait_ms();
        if(!dut.avoid_turn_left || drive_left!=-80 || drive_right!=80) $fatal(1,"450/500mm turn boundary");
        lidar_left=499;lidar_right=1500;#1;
        if(!sensor_stop || drive_left || drive_right) $fatal(1,"blocked selected side switched to the other side");
        lidar_front=599;wait_ms();if(!dut.avoid_turning) $fatal(1,"turn released below 600mm");
        lidar_front=600;wait_ms();if(dut.avoid_turning || drive_left!=60) $fatal(1,"600mm turn release boundary");
        lidar_left=16'hffff;#1;if(!sensor_stop || drive_left || drive_right) $fatal(1,"unknown sector moved");
        lidar_left=1500;armed=0;#1;if(drive_left || drive_right) $fatal(1,"ARM drop retained targets");
        wait_ms();armed=1;wait_ms();if(drive_enabled) $fatal(1,"ARM restoration restarted avoidance");
        send_cmd(8'h59,256'd1);motor_faults=1;#1;
        if(!force_stop || drive_left || drive_right) $fatal(1,"motor fault did not stop immediately");
        wait_ms();motor_faults=0;wait_ms();if(drive_enabled) $fatal(1,"fault clearance restarted avoidance");
        $display("PASS autonomous avoidance cruise, slow, wider-side turns, block and invalid-lidar stop");
        $finish;
    end

    initial begin
        #200000;
        $fatal(1,"avoidance watchdog state=%0d turn=%0d cmd=%0d/%0d",
            dut.avoid_running,dut.avoid_turning,drive_left,drive_right);
    end
endmodule
