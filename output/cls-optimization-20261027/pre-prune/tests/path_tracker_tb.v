`timescale 1ns/1ps
module path_tracker_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,load_begin=0,load_valid=0,load_last=0,enable=0,cancel=0;
    reg [6:0] load_x=70,load_y=64;reg [9:0] speed_limit=100;
    reg signed [31:0] pose_x=0,pose_y=25;reg signed [15:0] heading=0,goal_heading=0;
    wire signed [31:0] left_target,right_target;wire route_ready,arrived,fault;wire [14:0] remaining;
    a741_path_tracker dut(.turn_limit(10'd0),.blocked(),.*);
    integer requested,expected_cap;
    task update_drive;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(65) @(negedge clk);end
    endtask
    initial begin
        #30;rst_n=1;
        for(requested=0;requested<1024;requested=requested+1) begin
            @(negedge clk);speed_limit=requested;repeat(2) @(negedge clk);
            expected_cap=requested>100 ? 60:(requested*3)/5;
            if(dut.cap_cached!=expected_cap) $fatal(1,"cap at %0d: %0d != %0d",requested,dut.cap_cached,expected_cap);
        end
        speed_limit=100;repeat(2) @(negedge clk);
        load_begin=1;@(negedge clk);load_begin=0;load_valid=1;load_last=1;
        @(negedge clk);load_valid=0;load_last=0;repeat(3) @(negedge clk);enable=1;
        update_drive();if(left_target<=0 || right_target<=0 || left_target>100 || right_target>100) $fatal(1,"forward route target");
        pose_y=-100;update_drive();
        if(left_target<27 || left_target>30 || right_target<90 || right_target>93) $fatal(1,"left curve arithmetic %0d/%0d",left_target,right_target);
        pose_y=150;update_drive();
        if(right_target<27 || right_target>30 || left_target<90 || left_target>93) $fatal(1,"right curve arithmetic %0d/%0d",left_target,right_target);
        pose_y=25;
        heading=16384;update_drive();if(left_target<=0 || right_target>=0) $fatal(1,"route behind heading requires in-place right turn");
        speed_limit=10;update_drive();if(left_target>10 || right_target< -10) $fatal(1,"slow limit not applied to turning");
        speed_limit=0;update_drive();if(left_target || right_target) $fatal(1,"zero speed limit ignored");speed_limit=100;
        cancel=1;@(negedge clk);#1;if(left_target || right_target) $fatal(1,"cancel retained drive");cancel=0;
        pose_x=325;pose_y=25;heading=0;update_drive();if(!arrived || left_target || right_target) $fatal(1,"goal arrival");
        @(negedge clk);enable=0;load_begin=1;@(negedge clk);load_begin=0;load_valid=1;load_last=0;load_x=65;load_y=65;
        @(negedge clk);load_x=64;load_y=65;
        @(negedge clk);load_x=64;load_y=64;load_last=1;
        @(negedge clk);load_valid=0;load_last=0;pose_x=25;pose_y=25;enable=1;repeat(3) @(negedge clk);
        update_drive();if(dut.current_x!=64 || dut.current_y!=65 || remaining!=1) $fatal(1,"compressed positive Y edge");
        update_drive();if(dut.current_x!=65 || dut.current_y!=65 || remaining!=0) $fatal(1,"compressed positive X edge");
        @(negedge clk);enable=0;load_begin=1;@(negedge clk);load_begin=0;load_valid=1;load_last=0;load_x=63;load_y=63;
        @(negedge clk);load_x=64;load_y=63;
        @(negedge clk);load_x=64;load_y=64;load_last=1;
        @(negedge clk);load_valid=0;load_last=0;pose_x=25;pose_y=25;enable=1;repeat(3) @(negedge clk);
        update_drive();if(dut.current_x!=64 || dut.current_y!=63 || remaining!=1) $fatal(1,"compressed negative Y sign extension");
        update_drive();if(dut.current_x!=63 || dut.current_y!=63 || remaining!=0) $fatal(1,"compressed negative X sign extension");
        $display("PASS path tracking speed limits, heading turn, cancel and final goal tolerance");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
