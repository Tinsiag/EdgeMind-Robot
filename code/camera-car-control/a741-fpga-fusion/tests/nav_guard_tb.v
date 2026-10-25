`timescale 1ns/1ps
module nav_guard_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,start=0,cancel=0,clear_fault=0;
    reg geometry_verified=1,map_valid=1,pose_valid=1,lidar_valid=1,imu_valid=1,encoder_valid=1,path_valid=1,target_valid=1,link_alive=1;
    reg rotation_clear=1,localization_lost=0,search_segment_done=0,search_timeout=0;reg [15:0] front_mm=1000;
    wire active,force_stop,search_segment,locked;wire [3:0] search_count;wire [7:0] state,fault_code;wire [9:0] speed_limit_mm_s;
    a741_nav_guard dut(.*);
    wire [9:0] custom_limit;
    a741_nav_guard #(.FRONT_STOP_MM(500),.FRONT_SLOW_MM(900)) custom(
        .active(),.force_stop(),.search_segment(),.locked(),.search_count(),.state(),.fault_code(),
        .speed_limit_mm_s(custom_limit),.*);
    integer distance,expected;
    task pulse_start;begin @(negedge clk);start=1;@(negedge clk);start=0;end endtask
    initial begin
        #30;rst_n=1;geometry_verified=0;pulse_start;
        if(!locked || active) $fatal(1,"unverified geometry was accepted");
        @(negedge clk);clear_fault=1;@(negedge clk);clear_fault=0;geometry_verified=1;pulse_start;
        if(!active || force_stop) $fatal(1,"valid navigation did not start");
        // Check every millimetre, including both threshold boundaries.
        for(distance=0;distance<=1000;distance=distance+1) begin
            @(negedge clk);front_mm=distance;repeat(2) @(negedge clk);
            expected=distance<=250 ? 0:distance>=600 ? 100:((distance-250)*100)/350;
            if(speed_limit_mm_s!=expected) $fatal(1,"slowdown at %0d: %0d != %0d",distance,speed_limit_mm_s,expected);
            expected=distance<=500 ? 0:distance>=900 ? 100:((distance-500)*100)/400;
            if(custom_limit!=expected) $fatal(1,"custom thresholds at %0d: %0d != %0d",distance,custom_limit,expected);
        end
        front_mm=400;repeat(2) @(negedge clk);
        if(speed_limit_mm_s!=42) $fatal(1,"slowdown %0d",speed_limit_mm_s);
        front_mm=200;#1;if(speed_limit_mm_s!=0 || !force_stop) $fatal(1,"front stop gate");
        front_mm=1000;link_alive=0;@(negedge clk);
        if(!locked || !force_stop) $fatal(1,"link loss not latched");
        @(negedge clk);clear_fault=1;link_alive=1;@(negedge clk);clear_fault=0;pulse_start;
        localization_lost=1;pose_valid=0;#1;if(active || !force_stop) $fatal(1,"lost pose retained forward authority");
        @(negedge clk);#1;if(search_segment || active || !force_stop) $fatal(1,"lost localization did not settle first");
        repeat(20) begin tick=1;@(negedge clk);tick=0;@(negedge clk);end
        if(!search_segment || active) $fatal(1,"safe yaw search not entered");
        search_segment_done=1;@(negedge clk);search_segment_done=0;
        if(active || search_segment || !force_stop) $fatal(1,"segment boundary briefly authorized movement");
        repeat(20) begin tick=1;@(negedge clk);tick=0;@(negedge clk);end
        if(!search_segment || search_count!=1 || active) $fatal(1,"search did not resume after settling");
        search_timeout=1;@(negedge clk);#1;if(!locked || active || !force_stop) $fatal(1,"scan timeout not latched");
        $display("PASS geometry/link/obstacle locks, no forward recovery pulse, segment settle and scan timeout");$finish;
    end
    initial begin #50000;$fatal(1,"watchdog");end
endmodule
