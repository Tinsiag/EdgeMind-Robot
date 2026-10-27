`timescale 1ns/1ps
module lidar_guard_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,stream_valid=1,point_valid=0;
    reg [15:0] angle=0,distance=800;reg [7:0] confidence=100;
    reg signed [31:0] requested_left=100,requested_right=100;
    wire stop,scan_valid;wire [9:0] limit;wire [15:0] front,rear,nearest;
    a741_lidar_guard dut(.*);
    task point(input [15:0] a,input [15:0] d);
        begin @(negedge clk);angle=a;distance=d;point_valid=1;@(negedge clk);point_valid=0;end
    endtask
    task revolution(input [15:0] d);
        integer n;begin for(n=0;n<72;n=n+1) point(n*500,d);end
    endtask
    initial begin
        #30;rst_n=1;
        if(!stop) $fatal(1,"manual motion allowed before full scan");
        revolution(1000);point(0,1000);
        if(!scan_valid || stop || limit!=400) $fatal(1,"complete clear scan failed");
        point(27000,450);#1;if(!stop) $fatal(1,"near front not immediate");
        stream_valid=0;repeat(2) @(negedge clk);stream_valid=1;
        revolution(800);point(0,400);#1;if(!stop) $fatal(1,"wrap obstacle not immediate");
        revolution(800);point(0,800);#1;if(!stop) $fatal(1,"wrap obstacle lost from following scan");
        revolution(800);point(0,800);#1;if(stop || limit!=60) $fatal(1,"clear scan did not relax bounded speed");
        requested_left=-80;requested_right=80;#1;if(stop || limit!=80) $fatal(1,"clear rotation not allowed");
        point(1000,521);#1;if(!stop) $fatal(1,"rotation envelope boundary not stopped");
        stream_valid=0;repeat(2) @(negedge clk);stream_valid=1;
        revolution(1000);point(0,1000);#1;if(stop) $fatal(1,"full scan recovery failed");
        ms_tick=1;repeat(302) @(negedge clk);ms_tick=0;
        if(scan_valid || !stop) $fatal(1,"stale scan allowed manual drive");
        $display("PASS manual raw guard full coverage, conservative clearance, wrap retention and stale stop");$finish;
    end
    initial begin #200000;$fatal(1,"manual guard watchdog");end
endmodule
