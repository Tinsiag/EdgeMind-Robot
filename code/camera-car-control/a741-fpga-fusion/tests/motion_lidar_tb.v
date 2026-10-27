`timescale 1ns/1ps
module motion_lidar_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,cv=0,gu=0,tick=0;reg [7:0] kind=0;reg [255:0] payload=0;
    wire armed,calibrated,calibrating,l1,l2,r1,r2,pwm;wire [15:0] faults;
    wire signed [31:0] tl,tr;
    reg iv=1;reg signed [15:0] yaw=0;
    a741_motion #(.MOTION_LIDAR(1)) dut(.clk(clk),.rst_n(rst_n),.direct_valid(cv),.direct_kind(kind),.direct_payload(payload),
        .direct_ttl(16'd250),.direct_seq(8'd1),.direct_reply_ready(1'b1),.ms_tick(1'b0),.tick(tick),
        .imu_diagnostic(32'h07007068),.imu_errors(32'd1),.imu_sequence(32'd100),.imu_raw(96'd0),.imu_temperature(16'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .imu_valid(iv),.gyro_valid(iv),.imu_stationary(1'b1),.angle_update(1'b0),.gyro_update(gu),
        .yaw(yaw),.gz(16'sd0),.tof_valid(1'b0),.tof_mm(16'd0),.now_ms(32'd0),
        .armed(armed),.calibrated(calibrated),.calibrating(calibrating),.target_l(tl),.target_r(tr),.faults(faults),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),.lidar_control(pwm));
    task cmd(input [7:0] k,input [255:0] p);begin @(negedge clk);kind=k;payload=p;cv=1;@(negedge clk);cv=0;repeat(5) @(negedge clk);end endtask
    task cfg(input [7:0] k,input [31:0] v);begin cmd(8'h30,{216'd0,v,k});end endtask
    task control_tick;begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(250) @(negedge clk);end endtask
    integer n;
    initial begin
        #50;rst_n=1;cmd(2,0);if(armed) $fatal(1,"unconfigured ARM");
        cfg(0,1469);cfg(1,1471);cfg(2,66300);cfg(3,66300);cfg(4,234000);cfg(5,200);
        cfg(6,74103);cfg(7,1);cfg(8,0);cfg(9,512);cfg(10,5);cfg(11,8);control_tick;
        cmd(8'h43,0);for(n=0;n<64;n=n+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        if(!calibrated) $fatal(1,"calibration");
        cmd(8'h40,0);if(dut.reply_payload[47:32]!=16'h0751) $fatal(1,"motion lidar capability");
        cmd(8'h46,400);repeat(90) @(negedge clk);if(dut.lidar_duty!=400) $fatal(1,"PWM command");
        cmd(8'h46,900);if(dut.lidar_duty!=400) $fatal(1,"unbounded PWM");
        cmd(2,0);if(!armed) $fatal(1,"motor remained hard locked");
        cmd(8'h11,{192'd0,32'd100,32'd100});control_tick;
        if(tl!=100 || tr!=100 || faults || !armed) $fatal(1,"absent ToF blocks LD06 profile");
        yaw=640;cmd(8'h11,{192'd0,32'd90,32'd90});control_tick;
        if(tl!=90 || tr!=90) $fatal(1,"raw wheels unexpectedly apply heading correction");
        repeat(12) control_tick;
        if(dut.pi_l<=0 || dut.pi_r<=0) $fatal(1,"PI did not run");
        iv=0;repeat(5) @(negedge clk);if(armed || !faults[4] || l1 || l2 || r1 || r2) $fatal(1,"IMU loss safety");
        cmd(4,0);if(pwm) $fatal(1,"STOP did not stop radar");
        $display("PASS motor unlock after config/calibration, explicit no-ToF profile, LD06 PWM bounds and IMU/STOP protection");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
