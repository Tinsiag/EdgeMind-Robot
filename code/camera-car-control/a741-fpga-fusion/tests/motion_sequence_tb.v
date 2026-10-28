`timescale 1ns/1ps
module motion_sequence_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,tick=0,command=0,button_start=0;
    reg [7:0] kind=0; reg [255:0] payload=0;
    reg armed=1,link_alive=1,imu_valid=1,tilt_valid=1;
    reg [15:0] motor_faults=0; reg signed [31:0] manual_left=0,manual_right=0;
    // The sequence has the same lost-scan safety gate as the autonomous
    // personality; provide a valid clear scan for the deterministic motion.
    reg lidar_valid=1; reg [15:0] lidar_front=16'd1500,lidar_left=16'd1500,lidar_right=16'd1500;
    wire reply_done; wire [255:0] reply; wire drive_enabled,force_stop,sensor_stop;
    wire signed [31:0] drive_left,drive_right; wire [9:0] sensor_limit;
    wire [7:0] state,fault; wire [15:0] front_distance;
    a741_avoidance #(.SEQUENCE_TEST(1),.BUTTON_AUTONOMOUS(1)) dut(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(tick),.armed(armed),.link_alive(link_alive),
        .imu_valid(imu_valid),.tilt_valid(tilt_valid),.motor_faults(motor_faults),
        .manual_left(manual_left),.manual_right(manual_right),.yaw(0),.roll(0),.pitch(0),
        .lidar_valid(lidar_valid),.lidar_front(lidar_front),.lidar_left(lidar_left),.lidar_right(lidar_right),
        .manual_stop(0),.manual_scan_valid(0),.manual_limit(0),.supervisor_alive(1),.supervisor_fault(0),.supervisor_uptime(0),
        .command(command),.kind(kind),.payload(payload),.button_start(button_start),.reply_done(reply_done),.reply(reply),
        .drive_enabled(drive_enabled),.force_stop(force_stop),.drive_left(drive_left),.drive_right(drive_right),
        .sensor_stop(sensor_stop),.sensor_limit(sensor_limit),.state(state),.fault(fault),.front_distance(front_distance));
    task send;
        input [7:0] k; input [7:0] v; input [7:0] expected_reply;
        begin @(negedge clk);kind=k;payload=0;payload[7:0]=v;command=1;
            @(negedge clk);command=0;
            if(!reply_done || reply[7:0]!==expected_reply) $fatal(1,"sequence command reply=%h",reply[7:0]);
        end
    endtask
    task one_tick; begin @(negedge clk);tick=1;@(negedge clk);tick=0; end endtask
    integer n;
    initial begin
        #20;rst_n=1;@(negedge clk);button_start=1;@(negedge clk);button_start=0;@(negedge clk);
        if(!drive_enabled || drive_left!==0 || drive_right!==0) $fatal(1,"sequence did not enter safe transition");
        repeat(10) one_tick;
        if(drive_left!==120 || drive_right!==120) $fatal(1,"forward target mismatch");
        repeat(490) one_tick;
        if(dut.sequence_phase!==1 || drive_left!==0 || drive_right!==0) $fatal(1,"reverse transition missing phase=%0d ticks=%0d trans=%0d cmd=%0d/%0d",dut.sequence_phase,dut.phase_ticks,dut.transition_ticks,drive_left,drive_right);
        repeat(10) one_tick; if(drive_left!==-100 || drive_right!==-100) $fatal(1,"reverse target mismatch");
        repeat(490) one_tick; if(dut.sequence_phase!==2 || drive_left!==0 || drive_right!==0) $fatal(1,"left transition missing");
        repeat(10) one_tick; if(drive_left!==-80 || drive_right!==80) $fatal(1,"left target mismatch");
        repeat(490) one_tick; if(dut.sequence_phase!==3 || drive_left!==0 || drive_right!==0) $fatal(1,"right transition missing");
        repeat(10) one_tick; if(drive_left!==80 || drive_right!==-80) $fatal(1,"right target mismatch");
        armed=0;#1;if(!force_stop || drive_left || drive_right) $fatal(1,"ARM loss did not stop sequence");
        @(negedge clk);
        armed=1;repeat(10) one_tick;if(drive_enabled) $fatal(1,"sequence restarted after ARM restoration run=%0d pending=%0d phase=%0d",dut.sequence_running,dut.button_pending,dut.sequence_phase);
        @(negedge clk);button_start=1;@(negedge clk);button_start=0;#1;
        if(drive_enabled || drive_left || drive_right) $fatal(1,"sequence STOP failed");
        $display("PASS 5-second sequence phase order, zero transition, ARM stop and no restart");$finish;
    end
    initial begin #200000;$fatal(1,"sequence watchdog");end
endmodule
