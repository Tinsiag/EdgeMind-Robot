`timescale 1ns/1ps
module avoidance_core_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,host_pulse=0;
    reg [7:0] host_kind=0,host_seq=0;
    reg [255:0] host_payload=0;
    wire [895:0] snapshot;wire [255:0] fusion_snapshot;
    wire l1,l2,r1,r2;
    a741_core #(.CLK_HZ(500000),.FUSION_ENABLED(1),.MOTION_LIDAR(1),
        .GEOMETRY_VERIFIED(1),.RADIUS_MM(257)) dut(
        .clk(clk),.rst_n(rst_n),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),
        .phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),
        .eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),.eth_tx_ready(1'b1),
        .ddr_ready(rst_n),.frame_ready(1'b0),.camera_error(1'b0),.ddr_error(1'b0),
        .video_overflow(1'b0),.video_frames(32'd0),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot));
    initial begin
        force dut.iv=1;force dut.gv=1;force dut.yaw=0;force dut.calibrated=1;
        force dut.faults=0;force dut.armed=1;
        force dut.front=1500;force dut.lside=1500;force dut.rside=1500;force dut.lv=1;
        force dut.motion.command_age=0;force dut.motion.effective_ttl=250;
        force dut.reply_ready=1;
    end
    always @(host_pulse or host_kind or host_seq or host_payload) begin
        force dut.command_valid=host_pulse;force dut.command_kind=host_kind;
        force dut.command_seq=host_seq;force dut.command_ttl=16'd250;
        force dut.command_payload=host_payload;
    end
    task command(input [7:0] k,input [255:0] p,input [7:0] expected=0);
        integer age;
        begin
            @(negedge clk);host_kind=k;host_payload=p;host_seq=host_seq+1;host_pulse=1;
            @(negedge clk);host_pulse=0;age=0;
            while(!dut.freply_valid && age<2000) begin @(negedge clk);age=age+1;end
            if(!dut.freply_valid || dut.freply[7:0]!=expected) $fatal(1,"core command %h reply %h",k,dut.freply[7:0]);
            repeat(500) @(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;repeat(5000) @(negedge clk);
        if(!dut.basic_enabled.cpu_alive) $fatal(1,"bare CPU did not boot");
        command(8'h59,1);
        if(!dut.fowns || dut.fl!=120 || dut.fr!=120) $fatal(1,"avoidance did not own cruising targets");
        force dut.motion.command_age=1000;#1;
        if(dut.flink || dut.motion.enable) $fatal(1,"avoidance masks expired external lease");
        repeat(4) @(negedge clk);
        if(dut.fowns || dut.fl || dut.fr) $fatal(1,"link loss retained avoidance");
        force dut.motion.command_age=0;repeat(8) @(negedge clk);
        if(dut.fowns) $fatal(1,"link restoration restarted avoidance");
        command(8'h59,1);command(8'h59,0);
        if(dut.fowns || dut.fl || dut.fr) $fatal(1,"avoidance stop retained targets");
        command(8'h59,1);
        @(negedge clk);host_kind=4;host_payload=0;host_pulse=1;#1;
        if(dut.motion.enable || l1 || l2 || r1 || r2) $fatal(1,"STOP waited for a clock");
        @(negedge clk);host_pulse=0;repeat(4) @(negedge clk);
        if(dut.fowns) $fatal(1,"STOP retained avoidance state");
        repeat(500) @(negedge clk);command(8'h59,1);
        force dut.basic_enabled.cpu_alive=0;#1;
        if(!dut.fstop || dut.motion.enable || l1 || l2 || r1 || r2) $fatal(1,"CPU health did not inhibit output");
        repeat(4) @(negedge clk);if(dut.fowns) $fatal(1,"CPU loss retained avoidance");
        $display("PASS basic core real CPU boot, avoidance commands, STOP priority, external lease and CPU health");$finish;
    end
    initial begin #10000000;$fatal(1,"basic core watchdog");end
endmodule
