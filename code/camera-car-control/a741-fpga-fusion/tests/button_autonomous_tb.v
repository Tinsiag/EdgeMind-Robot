`timescale 1ns/1ps
module button_autonomous_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,tick=0,command=0,button_start=0;
    reg [7:0] kind=0; reg [255:0] payload=0;
    reg armed=1,link_alive=1,imu_valid=1,tilt_valid=1;
    reg [15:0] motor_faults=0; reg signed [31:0] manual_left=0,manual_right=0;
    reg lidar_valid=1; reg [15:0] lidar_front=16'd1500,lidar_left=16'd1500,lidar_right=16'd1500;
    wire reply_done; wire [255:0] reply; wire drive_enabled,force_stop,sensor_stop;
    wire signed [31:0] drive_left,drive_right; wire [9:0] sensor_limit;
    wire [7:0] state,fault; wire [15:0] front_distance;
    a741_avoidance #(.BUTTON_AUTONOMOUS(1)) dut(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(tick),.armed(armed),.link_alive(link_alive),
        .imu_valid(imu_valid),.tilt_valid(tilt_valid),.motor_faults(motor_faults),
        .manual_left(manual_left),.manual_right(manual_right),.yaw(0),.roll(0),.pitch(0),
        .lidar_valid(lidar_valid),.lidar_front(lidar_front),.lidar_left(lidar_left),.lidar_right(lidar_right),
        .manual_stop(0),.manual_scan_valid(1),.manual_limit(400),.supervisor_alive(1),.supervisor_fault(0),.supervisor_uptime(0),
        .command(command),.kind(kind),.payload(payload),.button_start(button_start),.reply_done(reply_done),.reply(reply),
        .drive_enabled(drive_enabled),.force_stop(force_stop),.drive_left(drive_left),.drive_right(drive_right),
        .sensor_stop(sensor_stop),.sensor_limit(sensor_limit),.state(state),.fault(fault),.front_distance(front_distance));
    initial begin
        #20;rst_n=1;@(negedge clk);button_start=1;@(negedge clk);button_start=0;@(negedge clk);
        if(!drive_enabled) $fatal(1,"S1 did not start avoidance");
        if(drive_left!==120 || drive_right!==120) $fatal(1,"S1 cruise mismatch");
        lidar_front=300;lidar_left=800;lidar_right=500;ms_tick=1;@(negedge clk);ms_tick=0;#1;
        if(!dut.avoid_turning || !dut.avoid_turn_left || drive_left!==-80 || drive_right!==80)
            $fatal(1,"S1 avoidance did not choose left opening");
        @(negedge clk);button_start=1;@(negedge clk);button_start=0;#1;
        if(drive_enabled || drive_left || drive_right) $fatal(1,"second S1 did not stop");
        $display("PASS S1 one-shot start, cruise, wider-side turn and second-press stop");$finish;
    end
    initial begin #20000;$fatal(1,"button watchdog");end
endmodule
