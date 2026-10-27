`timescale 1ns/1ps
module lidar_body_safety_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,stream_valid=1,point_valid=0,scan_end=0;
    reg [15:0] angle_cdeg=0,distance_mm=1000,rotation_radius_mm=257;
    reg signed [31:0] requested_left=100,requested_right=100,point_x=0,point_y=0;
    wire stop,rotation_clear,scan_valid;wire [15:0] front_mm,rear_mm,min_mm,clearance_mm;wire [9:0] speed_limit;
    a741_lidar_safety #(.BODY_COORDINATES(1),.FRONT_EXTENT(221),.REAR_EXTENT(70),.HALF_WIDTH(131)) dut(.*);
    task point(input integer a,x,y);
        begin @(negedge clk);angle_cdeg=a;point_x=x;point_y=y;point_valid=1;@(negedge clk);point_valid=0;end
    endtask
    integer i;
    initial begin
        #30;rst_n=1;
        for(i=0;i<72;i=i+1) point(i*500,$rtoi(1000*$cos(i*3.141592653589793/36)),$rtoi(1000*$sin(i*3.141592653589793/36)));
        @(negedge clk);point_valid=1;scan_end=1;@(negedge clk);point_valid=0;scan_end=0;
        repeat(4) @(negedge clk);
        if(stop || !rotation_clear || front_mm<750 || front_mm>779 || speed_limit!=400) $fatal(1,"CAD footprint not applied front=%0d",front_mm);
        point(0,550,0);repeat(4) @(negedge clk);
        if(stop || speed_limit>=400 || front_mm!=329) $fatal(1,"body clearance did not slow");
        point(0,450,0);#1;
        if(!stop || front_mm!=229) $fatal(1,"front footprint/laser offset ignored");
        requested_left=-100;requested_right=-100;#1;if(stop) $fatal(1,"unrelated rear blocked");
        point(18000,-250,0);#1;if(!stop || rear_mm!=180) $fatal(1,"rear body clearance ignored");
        requested_left=100;requested_right=80;point(9000,0,200);#1;
        if(!stop || rotation_clear) $fatal(1,"arc swept footprint ignored");
        stream_valid=0;@(negedge clk);#1;if(!stop || scan_valid) $fatal(1,"stale scan retained authorization");
        $display("PASS CAD body clearances, front/rear slowdown/stop, curved swept clearance and stream loss");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
