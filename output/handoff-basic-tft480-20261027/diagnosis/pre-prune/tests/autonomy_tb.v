`timescale 1ns/1ps
module autonomy_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,ms_tick=0,imu_valid=1,lidar_valid=0,calibrated=1,armed=0,link_alive=1;
    reg travel_tick=0,travel_valid=1;
    reg signed [31:0] left_travel=0,right_travel=0,manual_left=0,manual_right=0;
    reg signed [15:0] yaw=0;reg [15:0] motor_faults=0;
    reg lidar_point=0;reg [15:0] lidar_angle=0,lidar_distance=1000;reg [7:0] lidar_confidence=100;
    reg command=0;reg [7:0] kind=0;reg [255:0] payload=0;
    wire reply_done;wire [255:0] reply;wire drive_enabled,force_stop,sensor_stop;wire signed [31:0] drive_left,drive_right,pose_x,pose_y;
    wire [9:0] sensor_limit;wire signed [15:0] pose_heading;wire [7:0] nav_state,nav_fault,localization_quality;
    wire [15:0] front_distance;wire [31:0] map_revision;
    a741_autonomy dut(.*);
    wire mission_busy,mission_arrived,mission_failed;
    task cmd(input [7:0] k,input [255:0] p);
        integer age;
        begin
            @(negedge clk);kind=k;payload=p;command=1;@(negedge clk);command=0;
            age=0;while(!reply_done && age<200000) begin @(negedge clk);age=age+1;end
            if(!reply_done) $fatal(1,"command %h reply timeout",k);
            #1;
        end
    endtask
    reg [31:0] expected_crc;integer i,j;reg [31:0] v;
    initial begin
        #30;rst_n=1;cmd(8'h50,0);if(reply[7:0]!=0) $fatal(1,"map begin");repeat(16390) @(negedge clk);
        cmd(8'h51,{216'd0,8'h55,8'd1,16'd0,8'd1});if(reply[7:0]!=0) $fatal(1,"map write");
        cmd(8'h51,{224'd0,8'd1,16'd0,8'd0});if(reply[39:32]!=8'h55) $fatal(1,"packed map read %h",reply[39:32]);
        expected_crc=32'hffffffff;
        for(i=0;i<4096;i=i+1) begin
            v=expected_crc^(i==0 ? 8'h55:8'h00);
            for(j=0;j<8;j=j+1) v=v[0] ? (v>>1)^32'hedb88320:v>>1;
            expected_crc=v;
        end
        expected_crc=~expected_crc;
        cmd(8'h52,{224'd0,expected_crc^32'd1});if(reply[7:0]!=4) $fatal(1,"bad map CRC accepted");
        cmd(8'h52,{224'd0,expected_crc});if(reply[7:0]!=0 || reply[63:32]!=expected_crc) $fatal(1,"map CRC mismatch");
        cmd(8'h53,{176'd0,16'd16384,32'd50,32'd100});if(reply[7:0]!=0) $fatal(1,"pose set rejected");repeat(3) @(negedge clk);
        cmd(8'h57,0);if(reply[63:32]!=100 || reply[95:64]!=50 || reply[111:96]!=16384) $fatal(1,"pose query layout");
        cmd(8'h55,0);if(reply[7:0]!=1 || drive_enabled) $fatal(1,"unsafe navigation accepted");
        if(!sensor_stop) $fatal(1,"stale lidar authorized motor");
        $display("PASS map command write/read/CRC, initial pose, status layout and unverified-geometry motor lock");$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
