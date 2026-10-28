`timescale 1ns/1ps
module motion_button_session_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,tick=0,button_start=0,gyro_update=0;
    reg imu_valid=1,gyro_valid=1,imu_stationary=1;
    wire armed,calibrated,calibrating,lidar_control; wire [15:0] faults;
    wire signed [31:0] tl,tr; wire l1,l2,r1,r2;
    a741_motion #(.MOTION_LIDAR(1),.BUTTON_AUTONOMOUS(1)) dut(
        .direct_valid(1'b0),.direct_kind(0),.direct_seq(0),.direct_ttl(250),.direct_payload(0),
        .direct_reply_ready(1'b1),.fusion_owns(1'b0),.fusion_stop(1'b0),.obstacle_stop(1'b0),.fusion_left(0),.fusion_right(0),.obstacle_limit(400),
        .fusion_reply_valid(1'b0),.fusion_reply(0),.imu_diagnostic(0),.imu_errors(0),.imu_sequence(0),.imu_raw(0),.imu_temperature(0),
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(tick),.button_start(button_start),
        .left_a(0),.left_b(0),.right_a(0),.right_b(0),.imu_valid(imu_valid),.gyro_valid(gyro_valid),.angle_update(0),.gyro_update(gyro_update),
        .imu_stationary(imu_stationary),.yaw(0),.gz(0),.tof_valid(0),.tof_mm(0),.now_ms(0),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),.lidar_control(lidar_control),.armed(armed),.calibrated(calibrated),.calibrating(calibrating),
        .rotating(),.faults(faults),.left_count(),.right_count(),.left_speed(),.right_speed(),.left_pwm(),.right_pwm(),.target_l(tl),.target_r(tr),
        .state_code(),.config_revision(),.accumulated_yaw(),.gyro_bias(),.command_age(),.calibration_result(),
        .direct_reply_valid(),.direct_reply_kind(),.direct_reply_seq(),.direct_reply_length(),.direct_reply_payload(),.fusion_command(),.fusion_kind(),.fusion_payload(),
        .command_link_alive(),.manual_left(),.manual_right());
    task pulse_button; begin @(negedge clk);button_start=1;@(negedge clk);button_start=0; end endtask
    task pulse_gyro; begin @(negedge clk);gyro_update=1;@(negedge clk);gyro_update=0; end endtask
    integer n;
    initial begin
        #20;rst_n=1;
        pulse_button; // request starts before calibration and must persist
        for(n=0;n<64;n=n+1) pulse_gyro;
        repeat(3) @(negedge clk);
        if(!calibrated || !armed || !dut.button_session) $fatal(1,"S1 did not arm after bounded calibration");
        if(dut.lidar_duty!=400 || !dut.local_session) $fatal(1,"S1 did not keep LD06 session");
        repeat(400) begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end
        if(!armed || dut.command_age>=dut.effective_ttl) $fatal(1,"local lease was not renewed");
        pulse_button;
        #1;
        if(armed || dut.button_session || dut.lidar_duty!=0 || l1 || l2 || r1 || r2) $fatal(1,"second S1 did not stop safely");
        $display("PASS S1 request persistence, automatic calibration, bounded local lease and stop");$finish;
    end
    initial begin #1000000;$fatal(1,"motion button watchdog");end
endmodule
