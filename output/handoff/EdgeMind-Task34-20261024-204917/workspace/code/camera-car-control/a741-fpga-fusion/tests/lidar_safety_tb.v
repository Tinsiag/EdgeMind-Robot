`timescale 1ns/1ps
module lidar_safety_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,stream_valid=1,point_valid=0,scan_end=0;reg [15:0] angle_cdeg=0,distance_mm=1000,rotation_radius_mm=180;
    reg signed [31:0] requested_left=100,requested_right=100;
    reg signed [31:0] point_x=0,point_y=0;
    wire stop,rotation_clear,scan_valid;wire [15:0] front_mm,rear_mm,min_mm,clearance_mm;wire [9:0] speed_limit;
    a741_lidar_safety dut(.*);
    integer i;
    task point(input integer a,d);
        begin @(negedge clk);point_valid=1;angle_cdeg=a;distance_mm=d;@(negedge clk);point_valid=0;end
    endtask
    initial begin
        #30;rst_n=1;#1;if(!stop) $fatal(1,"incomplete scan authorized motion");
        for(i=0;i<72;i=i+1) point(i*500,1000);
        @(negedge clk);point_valid=1;scan_end=1;@(negedge clk);point_valid=0;scan_end=0;#1;
        if(stop || !scan_valid || !rotation_clear || speed_limit!=400) $fatal(1,"complete scan not accepted");
        point(0,400);repeat(3) @(negedge clk);#1;if(stop || speed_limit>=400) $fatal(1,"near obstacle did not slow down");
        point(0,200);#1;if(!stop || speed_limit!=0) $fatal(1,"new obstacle waited for scan wrap");
        requested_left=-100;requested_right=-100;#1;if(stop) $fatal(1,"forward obstacle incorrectly blocked clear rear");
        point(18000,200);#1;if(!stop) $fatal(1,"reverse obstacle ignored");
        requested_left=-40;requested_right=40;#1;if(rotation_clear || !stop) $fatal(1,"rotation swept envelope ignored");
        stream_valid=0;@(negedge clk);#1;if(scan_valid || !stop) $fatal(1,"lidar disconnect not invalidated");
        $display("PASS complete-scan lease, immediate obstacle, forward/reverse slowdown and swept rotation guard");$finish;
    end
    initial begin #20000;$fatal(1,"watchdog");end
endmodule
