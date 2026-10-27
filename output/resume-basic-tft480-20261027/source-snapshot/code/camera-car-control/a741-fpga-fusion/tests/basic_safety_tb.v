`timescale 1ns/1ps
module basic_safety_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,cv=0,ms=0,tick=0,gu=0;
    reg [7:0] kind=0;reg [255:0] payload=0;
    wire l1,l2,r1,r2;
    a741_core #(.CLK_HZ(1000000),.FUSION_ENABLED(1),.MOTION_LIDAR(1),
        .GEOMETRY_VERIFIED(1),.RADIUS_MM(257)) dut(
        .clk(clk),.rst_n(rst_n),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),
        .phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),
        .eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),.eth_tx_ready(1'b1),
        .ddr_ready(1'b1),.frame_ready(1'b0),.camera_error(1'b0),.ddr_error(1'b0),
        .video_overflow(1'b0),.video_frames(32'd0));
    initial begin
        // Stimulate interfaces only: ARM, calibration, faults and ownership are real RTL.
        force dut.iv=1;force dut.gv=1;force dut.yaw=0;force dut.gz=0;
        force dut.imu_stationary=1;force dut.gu=gu;force dut.au=0;
        force dut.lv=1;force dut.front=1500;force dut.lside=1500;force dut.rside=1500;
        force dut.command_valid=cv;force dut.command_kind=kind;force dut.command_payload=payload;
        force dut.command_ttl=16'd250;force dut.command_seq=1;force dut.reply_ready=1;
        force dut.ms_tick=ms;force dut.tick=tick;
    end
    task command(input [7:0] k,input [255:0] p);
        begin
            @(negedge clk);kind=k;payload=p;cv=1;#1;
            if((k==3 || k==4 || (k==8'h59 && p==0)) && (dut.motion.enable || l1 || l2 || r1 || r2))
                $fatal(1,"STOP/DISARM waited for a clock");
            @(negedge clk);cv=0;repeat(12) @(negedge clk);
        end
    endtask
    task configure(input [7:0] k,input [31:0] v);begin command(8'h30,{216'd0,v,k});end endtask
    task control_tick;begin
        @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(250) @(negedge clk);
    end endtask
    task start;
        begin
            command(2,0);if(!dut.armed) $fatal(1,"real ARM failed faults=%h",dut.faults);
            command(8'h59,1);repeat(4) control_tick;
            if(!dut.fowns || dut.tl!=120 || dut.tr!=120 || !dut.motion.enable)
                $fatal(1,"autonomous targets did not reach PI");
        end
    endtask
    task stopped;
        begin
            repeat(12) @(negedge clk);
            if(dut.armed || dut.fowns || dut.tl || dut.tr || l1 || l2 || r1 || r2)
                $fatal(1,"shutdown retained ARM/ownership/targets/PWM");
            command(5,0);control_tick;
            if(dut.armed || dut.fowns || dut.tl || dut.tr) $fatal(1,"heartbeat restored motion");
        end
    endtask
    integer n;
    initial begin
        if(dut.sensors.lidar.LIDAR_ZERO!=27000 || dut.sensors.lidar.LIDAR_CLOCKWISE!=1)
            $fatal(1,"mounting parameters did not reach the autonomous sector parser");
        #50;rst_n=1;
        configure(0,1469);configure(1,1471);configure(2,66300);configure(3,66300);
        configure(4,234000);configure(5,200);configure(6,74105);configure(7,1);
        configure(8,0);configure(9,512);configure(10,5);configure(11,8);
        control_tick;command(8'h43,0);
        for(n=0;n<64;n=n+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        repeat(5000) @(negedge clk);
        if(!dut.calibrated || !dut.basic_enabled.cpu_alive) $fatal(1,"calibration/CPU boot");
        start;command(4,0);stopped;
        start;command(3,0);stopped;
        start;command(8'h59,0);stopped;
        start;
        // Host wheel debugging cannot preempt or leave targets for later handover.
        command(8'h11,{192'd0,32'd300,32'd300});control_tick;
        if(dut.manual_l || dut.manual_r || !dut.fowns || dut.tl!=120) $fatal(1,"manual command preempted avoidance");
        // External link expiration must latch a fault and require explicit re-arm.
        for(n=0;n<252;n=n+1) begin
            @(negedge clk);ms=1;@(negedge clk);ms=0;repeat(128) @(negedge clk);
        end
        stopped;if(!dut.faults[0]) $fatal(1,"external TTL fault not latched");
        command(8'h21,0);start;
        force dut.basic_enabled.cpu_alive=0;#1;
        if(dut.motion.enable || l1 || l2 || r1 || r2) $fatal(1,"CPU loss left PWM enabled");
        stopped;if(!dut.faults[10]) $fatal(1,"CPU fault not latched");
        release dut.basic_enabled.cpu_alive;stopped;
        command(8'h21,0);start;
        force dut.gv=0;#1;
        if(dut.motion.enable) $fatal(1,"IMU loss left enable high");
        stopped;if(!dut.faults[4] || dut.calibrated) $fatal(1,"IMU fault/calibration invalidation");
        $display("PASS real calibration/ARM/PI, STOP/DISARM/avoidance-stop, manual arbitration, link TTL, CPU/IMU faults, no restart");$finish;
    end
    initial begin #10000000;$fatal(1,"basic safety watchdog");end
endmodule
