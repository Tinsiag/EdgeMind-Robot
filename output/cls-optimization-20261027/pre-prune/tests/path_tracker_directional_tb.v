`timescale 1ns/1ps
module path_tracker_directional_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,load_begin=0,load_valid=0,load_last=0,enable=0,cancel=0;
    reg [6:0] load_x=70,load_y=64;
    reg [9:0] speed_limit=1,turn_limit=40;
    reg signed [31:0] pose_x=0,pose_y=25;
    reg signed [15:0] heading=0,goal_heading=0;
    wire signed [31:0] left_target,right_target;
    wire route_ready,arrived,fault,blocked;wire [14:0] remaining;
    a741_path_tracker #(.DIRECTIONAL_LIMITS(1)) dut(.*);
    task update_drive;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(70) @(negedge clk);end
    endtask
    initial begin
        #30;rst_n=1;@(negedge clk);load_begin=1;
        @(negedge clk);load_begin=0;load_valid=1;load_last=1;
        @(negedge clk);load_valid=0;load_last=0;enable=1;repeat(3) @(negedge clk);
        update_drive();
        if(!blocked || left_target || right_target) $fatal(1,"rounded-zero translation was not reported blocked");
        heading=16384;update_drive();
        if(blocked || left_target!=40 || right_target!=-40) $fatal(1,"checked escape turn blocked by front translation cap");
        turn_limit=7;update_drive();
        if(blocked || left_target!=7 || right_target!=-7) $fatal(1,"turn clearance cap ignored");
        turn_limit=0;update_drive();
        if(!blocked || left_target || right_target) $fatal(1,"unsafe rotation was authorized");
        turn_limit=40;pose_x=325;heading=0;goal_heading=16384;update_drive();
        if(blocked || left_target!=-40 || right_target!=40) $fatal(1,"final heading did not use checked turn cap");
        cancel=1;@(negedge clk);
        if(blocked || left_target || right_target) $fatal(1,"cancel retained targets or blocked state");
        cancel=0;goal_heading=0;update_drive();
        if(!arrived || blocked || left_target || right_target) $fatal(1,"arrival incorrectly reported blocked");
        $display("PASS zero-speed blocked report, independent checked turns, rotation cap, final heading and cancel");$finish;
    end
    initial begin #100000;$fatal(1,"directional tracker watchdog");end
endmodule
