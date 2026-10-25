`timescale 1ns/1ps
module lidar_projection_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,valid=1,point_valid=0;reg [15:0] angle_cdeg=0,distance_mm=1000;reg [7:0] confidence=100;
    reg signed [15:0] heading=0,offset_x=100,offset_y=0;reg signed [31:0] pose_x=0,pose_y=0;
    reg [15:0] zero_cdeg=0;reg clockwise=0;
    wire point_done,scan_end,overflow;wire signed [31:0] endpoint_x,endpoint_y,origin_x,origin_y;wire [15:0] body_angle_cdeg,range_mm;
    a741_lidar_project dut(.*);
    wire signed [31:0] body_x,body_y;
    task check(input [15:0] a,input signed [15:0] h,input integer expected_x,expected_y);
        begin
            @(negedge clk);angle_cdeg=a;heading=h;point_valid=1;@(negedge clk);point_valid=0;
            wait(point_done);#1;
            if(endpoint_x<expected_x-3 || endpoint_x>expected_x+3 || endpoint_y<expected_y-3 || endpoint_y>expected_y+3)
                $fatal(1,"project angle=%0d heading=%0d got=%0d,%0d expected=%0d,%0d",a,h,endpoint_x,endpoint_y,expected_x,expected_y);
            @(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;
        check(0,0,1100,0);check(9000,0,100,1000);check(18000,0,-900,0);check(27000,0,100,-1000);
        check(0,16384,0,1100);check(0,-16384,0,-1100);check(0,-32768,-1100,0);
        zero_cdeg=27000;clockwise=1;check(27000,0,1100,0);
        valid=0;repeat(3) @(negedge clk);if(overflow) $fatal(1,"projector overflowed sparse input");
        $display("PASS LD06 all quadrants, world heading, installation offset and front alignment");$finish;
    end
    initial begin #50000;$fatal(1,"watchdog");end
endmodule
