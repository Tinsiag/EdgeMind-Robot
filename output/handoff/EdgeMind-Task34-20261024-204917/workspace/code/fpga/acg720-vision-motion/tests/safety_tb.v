`timescale 1ns/1ps
module safety_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,stop=0,start=0,clear_fault=0,set_mode=0,mode_request=0;
    reg manual_arm=0,manual_update=0,manual_refresh=0,heartbeat=0;
    reg [15:0] manual_ttl=250;
    reg signed [31:0] manual_left=100,manual_right=100,line_left=100,line_right=100;
    reg line_update=0;reg [1:0] regions_valid=3;
    reg tof_update=0,tof_valid=1,tof_error=0;reg [15:0] distance_mm=700,front_offset_mm=0;
    reg video_ready=1;reg [15:0] motor_faults=0;
    wire auto_mode,armed,drive_enable;wire signed [31:0] left_target,right_target;
    wire [7:0] reason,state_code;wire [15:0] line_age,tof_age,command_age,clearance,base_speed;wire [1:0] safe_samples;
    safety_supervisor dut(.*);
    task tick;begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end endtask
    task sensors;begin @(negedge clk);tof_update=1;line_update=1;@(negedge clk);tof_update=0;line_update=0;repeat(2)@(negedge clk);end endtask
    task begin_auto;begin repeat(4)sensors;@(negedge clk);start=1;@(negedge clk);start=0;repeat(2)@(negedge clk);if(!drive_enable)$fatal(1,"Auto failed to start reason=%d safe=%d",reason,safe_samples);end endtask
    integer i;
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        if(drive_enable)$fatal(1,"Boot enabled output");
        mode_request=1;set_mode=1;@(negedge clk);set_mode=0;
        begin_auto;
        for(i=0;i<1000;i=i+1) begin tick;if(i%20==0)sensors;end
        if(!drive_enable)$fatal(1,"Auto incorrectly depends on PC TTL");
        @(negedge clk);distance_mm=240;tof_update=1;
        #1;if(drive_enable)$fatal(1,"Obstacle gate waited for state update");
        @(negedge clk);tof_update=0;
        if(armed || reason!=2)$fatal(1,"Obstacle not latched");
        distance_mm=700;repeat(5)sensors;
        if(drive_enable)$fatal(1,"Obstacle removal auto resumed");
        begin_auto;
        regions_valid=0;sensors;
        if(drive_enable)$fatal(1,"Lost line kept old target");
        for(i=0;i<100;i=i+1) begin tick;if(i%20==0)sensors;end
        if(reason!=3 || armed)$fatal(1,"Lost-line timeout not latched");
        regions_valid=3;begin_auto;
        tof_valid=0;sensors;
        if(drive_enable || reason!=5)$fatal(1,"Invalid distance treated as clear");
        clear_fault=1;@(negedge clk);clear_fault=0;tof_valid=1;begin_auto;
        for(i=0;i<151;i=i+1) begin tick;if(i%20==0)begin line_update=1;@(negedge clk);line_update=0;end end
        if(drive_enable || reason!=5)$fatal(1,"Stale ToF kept motion");
        clear_fault=1;@(negedge clk);clear_fault=0;begin_auto;
        stop=1;#1;if(drive_enable)$fatal(1,"STOP gate not immediate");
        @(negedge clk);stop=0;
        set_mode=1;mode_request=0;@(negedge clk);set_mode=0;
        repeat(4)sensors;manual_arm=1;@(negedge clk);manual_arm=0;
        manual_left=999;manual_right=-999;manual_update=1;manual_refresh=1;
        @(negedge clk);manual_update=0;manual_refresh=0;
        if(left_target!=150 || right_target!=-150)$fatal(1,"Manual limits missing");
        distance_mm=350;sensors;
        if(left_target!=64 || right_target!=-64)$fatal(1,"Manual ToF slow limit missing");
        distance_mm=700;sensors;
        for(i=0;i<251;i=i+1) begin tick;if(i%20==0)sensors;end
        if(drive_enable || reason!=7)$fatal(1,"Manual TTL not enforced");
        $display("PASS: autonomous ownership, obstacle latch, lost line, stale/invalid ToF, STOP, TTL and limits");$finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
