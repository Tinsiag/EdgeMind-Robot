`timescale 1ns/1ps
module motion_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,ms=0,tick=0,iv=1,gv=1,au=0,gu=0,tv=1;
    reg signed [15:0] yaw=32000,gz=0;reg [15:0] range_mm=1000;
    wire armed,calibrated,calibrating,rotating;wire [15:0] faults;wire signed [31:0] tl,tr,acc;
    wire l1,l2,r1,r2;reg cv=0;reg [7:0] kind=0;reg [255:0] payload=0;
    a741_motion dut(.clk(clk),.rst_n(rst),.uart_rx(1'b1),.ms_tick(ms),.tick(tick),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .imu_valid(iv),.gyro_valid(gv),.imu_stationary(1'b1),.angle_update(au),.gyro_update(gu),.yaw(yaw),.gz(gz),
        .tof_valid(tv),.tof_mm(range_mm),.now_ms(32'd0),.armed(armed),.calibrated(calibrated),
        .calibrating(calibrating),.rotating(rotating),.faults(faults),
        .target_l(tl),.target_r(tr),.accumulated_yaw(acc),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2));
    task cmd(input [7:0] k,input [255:0] p);
        begin @(negedge clk);kind=k;payload=p;cv=1;@(negedge clk);cv=0;repeat(3) @(negedge clk);end
    endtask
    task control_tick;begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(250) @(negedge clk);end endtask
    task clock_ms;begin @(negedge clk);ms=1;@(negedge clk);ms=0;end endtask
    task sample_ms;begin
        @(negedge clk);tick=1;ms=1;@(negedge clk);tick=0;ms=0;repeat(250) @(negedge clk);
    end endtask
    task cfg(input [7:0] k,input [31:0] v);begin cmd(8'h30,{216'd0,v,k});end endtask
    task arm;begin cmd(2,0);if(!armed) $fatal(1,"ARM rejected");end endtask
    integer n,wait_cycles;
    task target_boundary;
        begin
            @(negedge clk);tick=1;@(negedge clk);tick=0;wait_cycles=0;
            while(!dut.targets_valid && wait_cycles<250) begin @(negedge clk);wait_cycles=wait_cycles+1;end
            if(!dut.targets_valid) $fatal(1,"target valid boundary not reached");
        end
    endtask
    initial begin
        force dut.cv=cv;force dut.kind=kind;force dut.payload=payload;force dut.ttl=16'd250;
        #50;rst=1;cmd(2,0);if(armed) $fatal(1,"unconfigured ARM");
        cfg(0,1469);cfg(1,1471);cfg(2,66300);cfg(3,66300);cfg(4,121400);
        cfg(5,200);cfg(6,74101);cfg(7,1);cfg(8,0);cfg(9,512);cfg(10,5);cfg(11,8);
        control_tick();cmd(8'h43,0);
        for(n=0;n<64;n=n+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        if(!calibrated || calibrating) $fatal(1,"zero bias calibration");
        // Startup grace must outlast the configured ramps, but still detect a stalled wheel.
        arm();cmd(8'h11,{192'd0,32'd100,32'd100});
        for(n=0;n<20;n=n+1) begin sample_ms();if(n==18) cmd(8'h05,0);end
        if(faults || !armed) $fatal(1,"encoder startup grace expired too early");
        // The current profile allows 100 samples at the 100 Hz control tick.
        for(n=20;n<95;n=n+1) begin sample_ms();if(n%20==19) cmd(8'h05,0);end
        if(faults || !armed) $fatal(1,"encoder fault before the 1000ms feedback window");
        for(n=95;n<105;n=n+1) begin sample_ms();if(n%20==19) cmd(8'h05,0);end
        if(!faults[2] || armed) $fatal(1,"encoder stall not latched after the 1000ms feedback window");
        cmd(8'h21,0);
        // A replacement command arrives on the exact edge that could commit the old result.
        arm();cmd(8'h11,{192'd0,32'd80,32'd120});target_boundary;
        kind=8'h11;payload={192'd0,-32'sd40,-32'sd60};cv=1;
        @(negedge clk);cv=0;
        repeat(260) begin @(negedge clk);if(tl || tr) $fatal(1,"replaced valid result committed stale wheels");end
        control_tick();if(tl!=-60 || tr!=-40) $fatal(1,"replacement wheel command lost");cmd(4,0);
        // STOP takes priority over a valid calculation and blocks the output immediately.
        arm();cmd(8'h11,{192'd0,32'd80,32'd120});target_boundary;
        kind=4;payload=0;cv=1;#1;if(dut.enable || l1 || l2 || r1 || r2) $fatal(1,"STOP waited for target commit");
        @(negedge clk);cv=0;
        repeat(260) begin @(negedge clk);if(armed || tl || tr) $fatal(1,"STOP valid result restarted wheels");end
        // A front obstacle at that boundary must latch a fault, with no late restart.
        arm();cmd(8'h11,{192'd0,32'd80,32'd120});target_boundary;
        range_mm=250;#1;if(dut.enable) $fatal(1,"ToF hard stop waited for target commit");
        repeat(260) begin @(negedge clk);if(armed || tl || tr) $fatal(1,"ToF valid result restarted wheels");end
        if(!faults[5]) $fatal(1,"boundary ToF fault not latched");range_mm=1000;cmd(8'h21,0);
        // TTL expiration during a valid pulse disables PWM as soon as age reaches the limit.
        arm();cmd(8'h11,{192'd0,32'd80,32'd120});
        for(n=0;n<249;n=n+1) clock_ms();
        target_boundary;ms=1;@(negedge clk);ms=0;
        if(dut.enable || l1 || l2 || r1 || r2) $fatal(1,"TTL valid boundary left output enabled");
        repeat(260) begin @(negedge clk);if(armed || tl || tr) $fatal(1,"expired valid result restarted wheels");end
        if(!faults[0]) $fatal(1,"boundary TTL fault not latched");cmd(8'h21,0);
        arm();range_mm=375;cmd(8'h45,{192'd0,32'd100,32'd100});control_tick();
        if(tl!=50 || tr!=50) $fatal(1,"ToF scaling %d %d",tl,tr);
        tv=0;repeat(4) @(negedge clk);
        if(armed || !faults[5] || l1 || l2 || r1 || r2) $fatal(1,"ToF stale stop");
        tv=1;range_mm=1000;cmd(8'h21,0);
        arm();cmd(8'h42,{208'd0,16'd100,32'd16384});control_tick();
        @(negedge clk);yaw=-32000;au=1;@(negedge clk);au=0;
        if(acc!=1536) $fatal(1,"IMU unwrap %d",acc);
        iv=0;repeat(4) @(negedge clk);
        if(armed || rotating || !faults[4]) $fatal(1,"IMU loss must stop rotation");
        if(calibrated) $fatal(1,"sensor loss retained calibration");
        iv=1;cmd(8'h21,0);cmd(8'h43,0);
        for(n=0;n<64;n=n+1) begin @(negedge clk);gu=1;@(negedge clk);gu=0;end
        arm();cmd(8'h11,{192'd0,-32'sd100,-32'sd100});control_tick();
        for(n=0;n<251;n=n+1) clock_ms();
        if(armed || !faults[0]) $fatal(1,"TTL stop");
        cmd(8'h21,0);arm();cmd(8'h11,{192'd0,-32'sd100,-32'sd100});control_tick();cmd(4,0);
        if(armed || tl || tr || l1 || l2 || r1 || r2) $fatal(1,"cancel");
        arm();for(n=0;n<251;n=n+1) clock_ms();
        if(armed || !faults[0]) $fatal(1,"idle ARM must expire");
        cmd(8'h11,{192'd0,32'd100,32'd100});control_tick();
        if(armed || tl || tr) $fatal(1,"delayed command restarted expired ARM");
        cmd(8'h21,0);arm();cmd(8'h42,{208'd0,16'd100,32'd16384});
        @(negedge clk);yaw=yaw+16384;au=1;@(negedge clk);au=0;control_tick();
        for(n=0;n<202;n=n+1) clock_ms();
        control_tick();
        if(rotating || faults || tl || tr || dut.desired_l || dut.desired_r) $fatal(1,"rotation completed or restarted");
        cmd(4,0);arm();cmd(8'h42,{208'd0,16'd100,32'd16384});
        @(negedge clk);yaw=yaw+18000;au=1;@(negedge clk);au=0;control_tick();
        for(n=0;n<202;n=n+1) clock_ms();
        repeat(3) @(negedge clk);
        if(!faults[9] || armed) $fatal(1,"rotation tolerance failure must latch");
        cmd(8'h43,0);
        @(negedge clk);yaw=yaw+400;au=1;@(negedge clk);au=0;
        if(calibrating || calibrated || dut.calibration_result!=2) $fatal(1,"moving calibration accepted");
        cmd(8'h43,0);gv=0;repeat(3) @(negedge clk);
        if(calibrating || dut.calibration_result!=3) $fatal(1,"stale calibration kept running");
        $display("PASS config/calibration, atomic command replacement, STOP/ToF/TTL valid boundaries, IMU unwrap/loss and cancel");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
