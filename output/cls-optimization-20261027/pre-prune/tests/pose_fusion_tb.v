`timescale 1ns/1ps
module pose_fusion_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,tick=0,sample_valid=1,pose_set=0;
    reg signed [31:0] left_mm=100,right_mm=100;
    reg signed [15:0] yaw=0,set_heading=0;reg signed [31:0] set_x_mm=0,set_y_mm=0;
    wire signed [31:0] x_mm,y_mm;wire signed [15:0] heading;wire pose_valid,overrun;
    a741_pose_fusion dut(.clk(clk),.rst_n(rst_n),.tick(tick),.sample_valid(sample_valid),.pose_set(pose_set),
        .left_distance_mm(left_mm),.right_distance_mm(right_mm),.yaw(yaw),
        .set_x_mm(set_x_mm),.set_y_mm(set_y_mm),.set_heading(set_heading),
        .x_mm(x_mm),.y_mm(y_mm),.heading(heading),.pose_valid(pose_valid),.overrun(overrun));
    task update_pose;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(24) @(negedge clk);end
    endtask
    initial begin
        #50;rst_n=1;update_pose;
        if(!pose_valid || x_mm<98 || x_mm>102 || y_mm>2 || y_mm< -2) $fatal(1,"forward pose %0d,%0d",x_mm,y_mm);
        yaw=16'sd16384;update_pose;
        if(x_mm<98 || x_mm>101 || y_mm<98 || y_mm>103) $fatal(1,"90-degree pose %0d,%0d",x_mm,y_mm);
        sample_valid=0;update_pose;
        if(pose_valid) $fatal(1,"invalid sample retained valid pose");
        sample_valid=1;set_x_mm=0;set_y_mm=0;set_heading=16'sd16384;yaw=0;
        @(negedge clk);pose_set=1;@(negedge clk);pose_set=0;update_pose;
        if(x_mm>2 || x_mm< -2 || y_mm<98 || y_mm>102) $fatal(1,"map heading offset %0d,%0d",x_mm,y_mm);
        $display("PASS encoder/IMU pose projection, map heading offset and invalid-sample gate");$finish;
    end
    initial begin #200000;$fatal(1,"watchdog");end
endmodule
