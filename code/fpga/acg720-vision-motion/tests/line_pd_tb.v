`timescale 1ns/1ps
module line_pd_tb;
    reg clk=0;always #5 clk=~clk;reg rst_n=0,update=0,mirror=0;
    reg [1:0] regions_valid=3;reg [10:0] near_center=400,far_center=400;
    reg [15:0] kp_q8=64,kd_q8=96,base_speed=100;
    wire signed [31:0] left_target,right_target;
    line_pd dut(.*);
    task apply;begin @(negedge clk);update=1;@(negedge clk);update=0;end endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;apply;
        if(left_target!=100 || right_target!=100)$fatal(1,"Centered line not straight");
        near_center=450;far_center=470;apply;
        if(left_target<=right_target)$fatal(1,"Right line steers left");
        mirror=1;apply;if(left_target>=right_target)$fatal(1,"Mirror not applied");
        mirror=0;near_center=600;far_center=700;apply;
        if(left_target<0 || right_target<0 || left_target>150 || right_target>150)$fatal(1,"Wheel limits");
        regions_valid=1;near_center=400;apply;if(left_target!=40 || right_target!=40)$fatal(1,"Single ROI not slowed");
        regions_valid=0;apply;if(left_target!=0 || right_target!=0)$fatal(1,"Lost line retained targets");
        $display("PASS: line steering sign, spatial PD, mirror, slow/limit and lost-line zero");$finish;
    end
endmodule
