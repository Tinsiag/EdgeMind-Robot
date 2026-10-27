`timescale 1ns/1ps
module local_lease_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,cv=0,gu=0,ms=0,own=0,local_alive=0,tick=0,obstacle=0;
    reg [7:0] kind=0;reg [255:0] payload=0;
    wire armed,calibrated;wire [15:0] faults;
    a741_motion #(.MOTION_LIDAR(1),.FUSION_ENABLED(1)) dut(
        .clk(clk),.rst_n(rst_n),.uart_rx(1'b1),.ms_tick(ms),.tick(tick),
        .fusion_owns(own),.fusion_stop(1'b0),.obstacle_stop(obstacle),.autonomy_alive(local_alive),
        .fusion_left(32'd0),.fusion_right(32'd0),.obstacle_limit(10'd400),.fusion_reply_valid(1'b0),.fusion_reply(256'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .imu_valid(1'b1),.gyro_valid(1'b1),.imu_stationary(1'b1),.angle_update(1'b0),.gyro_update(gu),
        .yaw(16'd0),.gz(16'd0),.tof_valid(1'b0),.tof_mm(16'd0),.now_ms(32'd0),
        .imu_diagnostic(32'd0),.imu_errors(32'd0),.imu_sequence(32'd0),.imu_raw(96'd0),.imu_temperature(16'd0),
        .armed(armed),.calibrated(calibrated),.faults(faults));
    task cmd(input [7:0] k,input [255:0] p);
        begin @(negedge clk);kind=k;payload=p;cv=1;@(negedge clk);cv=0;repeat(5) @(negedge clk);end
    endtask
    task cfg(input [7:0] key,input [31:0] value);begin cmd(8'h30,{216'd0,value,key});end endtask
    task milliseconds(input integer count);
        integer i;begin for(i=0;i<count;i=i+1) begin @(negedge clk);ms=1;@(negedge clk);ms=0;end end
    endtask
    integer i;
    initial begin
        force dut.cv=cv;force dut.kind=kind;force dut.payload=payload;force dut.ttl=16'd250;force dut.reply_ready=1'b1;
        #50;rst_n=1;
        cfg(0,1469);cfg(1,1471);cfg(2,66300);cfg(3,66300);cfg(4,234000);cfg(5,200);
        cfg(6,74103);cfg(7,1);cfg(8,0);cfg(9,512);cfg(10,5);cfg(11,8);
        cmd(8'h43,0);for(i=0;i<64;i=i+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        if(!calibrated) $fatal(1,"calibration");
        cmd(2,0);
        // STOP at the manual arithmetic commit boundary must still discard a
        // result when its internal enable is registered by one cycle.
        cmd(8'h11,{192'd0,32'd100,32'd100});
        @(negedge clk);tick=1;@(negedge clk);tick=0;
        i=0;while(dut.targets.state!=dut.targets.DONE && i<250) begin @(negedge clk);i=i+1;end
        if(i==250) $fatal(1,"manual target fixture did not reach commit");
        kind=4;payload=0;cv=1;@(negedge clk);cv=0;
        repeat(260) begin
            @(negedge clk);
            if(armed || dut.target_l || dut.target_r || dut.left_in1 || dut.left_in2)
                $fatal(1,"manual target survived STOP at commit");
        end
        cmd(2,0);own=1;local_alive=1;milliseconds(600);
        if(!armed || faults || !dut.command_link_alive) $fatal(1,"onboard lease incorrectly depended on host heartbeat");
        @(negedge clk);dut.target_l=100;dut.target_r=100;tick=1;
        @(negedge clk);tick=0;repeat(300) @(negedge clk);
        if(dut.pi_l!=0 || dut.pi_r!=0) $fatal(1,"stale target produced a pulse during zero-target planning");
        // Start with an already active PWM pulse. The obstacle gate must drop
        // it between clocks, and a one-clock stop must clear old PI output
        // before the registered arithmetic enable can reopen the output gate.
        @(negedge clk);dut.pl.command=100;dut.pl.applied=100;
        dut.ml.dead=0;dut.ml.direction_q=0;dut.ml.phase=1;dut.ml.duty_q=50000;
        #1;if(!dut.left_in1) $fatal(1,"PWM gate fixture not active");
        obstacle=1;#1;if(dut.left_in1 || dut.left_in2) $fatal(1,"obstacle gate waited for clk");
        @(negedge clk);obstacle=0;#1;
        if(dut.left_in1 || dut.left_in2) $fatal(1,"stale PWM returned before PI clear");
        repeat(3) @(negedge clk);
        if(dut.pi_l || dut.left_in1 || dut.left_in2) $fatal(1,"PI command survived stop/release");
        @(negedge clk);own=0;local_alive=0;kind=2;payload=0;cv=1;
        @(negedge clk);cv=0;repeat(5) @(negedge clk);
        if(armed || faults) $fatal(1,"normal completion/simultaneous ARM left armed=%0d faults=%h",armed,faults);
        cmd(2,0);own=1;local_alive=1;milliseconds(300);
        @(negedge clk);dut.pl.command=100;dut.pl.applied=100;
        dut.ml.dead=0;dut.ml.magnitude_q=100;dut.ml.direction_q=0;dut.ml.phase=1;dut.ml.duty_q=50000;
        repeat(3) @(negedge clk);
        if(dut.reply_left_pwm!=100) $fatal(1,"PWM telemetry fixture not active");
        cmd(4,0);if(armed) $fatal(1,"onboard lease bypassed STOP");
        if(dut.reply_payload[183:152]!=0) $fatal(1,"STOP reply reported pre-stop PWM");
        own=0;repeat(5) @(negedge clk);cmd(2,0);own=1;
        cmd(8'h58,3);if(armed) $fatal(1,"mission cancel did not immediately disarm motor stage");
        own=0;repeat(5) @(negedge clk);cmd(2,0);own=1;milliseconds(300);
        local_alive=0;repeat(5) @(negedge clk);
        if(armed || !faults[0]) $fatal(1,"loss of onboard lease did not enforce motor timeout");
        $display("PASS motor-stage local lease, normal release without false timeout, release priority over ARM, unconditional STOP and local lease loss shutdown");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
