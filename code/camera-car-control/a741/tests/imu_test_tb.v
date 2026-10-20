`timescale 1ns/1ps
module imu_test_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,cv=0,gu=0;reg [7:0] kind=0;reg [255:0] payload=0;
    wire armed,calibrated,calibrating,l1,l2,r1,r2;
    wire signed [31:0] tl,tr;
    a741_motion #(.IMU_TEST(1)) dut(.clk(clk),.rst_n(rst_n),.uart_rx(1'b1),.ms_tick(1'b0),.tick(1'b0),
        .imu_diagnostic(32'h07006869),.imu_errors(32'd2),.imu_sequence(32'd123),
        .imu_raw(96'h0066fffe01024000fffe0001),.imu_temperature(16'hfffe),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .imu_valid(1'b1),.gyro_valid(1'b1),.imu_stationary(1'b1),.angle_update(1'b0),.gyro_update(gu),
        .yaw(16'sd0),.gz(16'sd0),.tof_valid(1'b0),.tof_mm(16'd0),.now_ms(32'd0),
        .armed(armed),.calibrated(calibrated),.calibrating(calibrating),.target_l(tl),.target_r(tr),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2));
    task cmd(input [7:0] k,input [255:0] p);begin
        @(negedge clk);kind=k;payload=p;cv=1;@(negedge clk);cv=0;repeat(3) @(negedge clk);
    end endtask
    task cfg(input [7:0] k,input [31:0] v);begin cmd(8'h30,{216'd0,v,k});end endtask
    task read_key(input [31:0] k,input [31:0] expected);begin
        cmd(8'h44,k);if(dut.reply_payload[63:32]!==expected) $fatal(1,"key %0d got %h",k,dut.reply_payload[63:32]);
    end endtask
    integer n;
    initial begin
        force dut.cv=cv;force dut.kind=kind;force dut.payload=payload;force dut.ttl=16'd250;
        force dut.reply_ready=1'b1;
        #50;rst_n=1;
        cfg(0,1469);cfg(1,1471);cfg(2,66300);cfg(3,66300);
        cfg(5,200);cfg(6,74102);cfg(7,1);cfg(8,0);cfg(9,512);cfg(10,5);cfg(11,8);
        if(dut.configured[4]) $fatal(1,"test fabricated mechanical track");
        cmd(8'h43,0);if(!calibrating) $fatal(1,"IMU-only calibration requires wheel track");
        for(n=0;n<64;n=n+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        if(!calibrated || calibrating) $fatal(1,"IMU-only calibration failed");
        cmd(8'h40,0);if(dut.reply_payload[47:32]!=16'h00d1) $fatal(1,"test capability");
        read_key(14,32'h07006869);read_key(15,2);read_key(16,123);
        read_key(17,32'hfffe0001);read_key(18,32'h01024000);read_key(19,32'h0066fffe);read_key(20,32'hfffe);
        cfg(4,120000);
        force dut.calibrated=1'b1;
        cmd(2,0);cmd(8'h45,{192'd0,32'd100,32'd100});cmd(8'h42,{208'd0,16'd100,32'd16384});
        if(armed || tl || tr || l1 || l2 || r1 || r2) $fatal(1,"test accepted motor command");
        force dut.armed=1'b1;force dut.pi_l=32'sd512;force dut.pi_r=-32'sd512;
        repeat(200) begin @(negedge clk);if(dut.enable || l1 || l2 || r1 || r2) $fatal(1,"motor lock bypass");end
        $display("PASS IMU test calibration without track, diagnostic registers, ARM rejection and forced motor lock");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
