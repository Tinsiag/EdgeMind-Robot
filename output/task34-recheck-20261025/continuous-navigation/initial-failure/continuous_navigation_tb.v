`timescale 1ns/1ps
// Synthetic 3x2.4m room with the compiled CAD footprint/offset.
// Ideal differential-drive plant with per-point moving-room ray casts.
// Synthetic model only: no measured wheel slip, inertia or sensor delays.
module continuous_navigation_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;integer cycles=0;
    wire ms_tick=cycles%500==499,tick=cycles%5000==4999;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;
    reg imu_valid=1,lidar_valid=0,calibrated=1,armed=0,link_alive=1;
    reg travel_tick=0,travel_valid=1;reg signed [31:0] left_travel=0,right_travel=0,manual_left=0,manual_right=0;
    reg signed [15:0] yaw=0;reg [15:0] motor_faults=0;
    reg lidar_point=0;reg [15:0] lidar_angle=0,lidar_distance=1000;reg [7:0] lidar_confidence=100;
    reg command=0;reg [7:0] kind=0;reg [255:0] payload=0;
    wire reply_done;wire [255:0] reply;wire drive_enabled,force_stop,sensor_stop;
    wire signed [31:0] drive_left,drive_right,pose_x,pose_y;wire [9:0] sensor_limit;
    wire signed [15:0] pose_heading;wire [7:0] nav_state,nav_fault,localization_quality;
    wire [15:0] front_distance;wire [31:0] map_revision;
    a741_autonomy #(.GEOMETRY_VERIFIED(1),.RADIUS_MM(257),.LIDAR_X(164),.FRONT_EXTENT(221),.REAR_EXTENT(70),.HALF_WIDTH(131)) dut(.*);
    wire mission_busy,mission_arrived,mission_failed;
    task cmd(input [7:0] k,input [255:0] p);
        integer age;
        begin
            @(negedge clk);kind=k;payload=p;command=1;@(negedge clk);command=0;
            age=0;while(!reply_done && age<200000) begin @(negedge clk);age=age+1;end
            if(!reply_done || reply[7:0]!=0) $fatal(1,"synthetic navigation command %h failed reply=%h",k,reply[7:0]);
        end
    endtask
    real true_x=25.0,true_y=25.0,true_theta=0.0;
    real vl,vr,ds,dtheta,midpoint;
    integer robot_ticks=0,move_ticks=0;
    always @(negedge clk) begin
        travel_tick=0;
        if(rst_n && tick) begin
            vl=(armed && drive_enabled && !force_stop && !sensor_stop) ? $itor($signed(drive_left)):0.0;
            vr=(armed && drive_enabled && !force_stop && !sensor_stop) ? $itor($signed(drive_right)):0.0;
            ds=(vl+vr)*0.005;dtheta=(vr-vl)*0.01/234.0;
            midpoint=true_theta+dtheta*0.5;
            true_x=true_x+ds*$cos(midpoint);true_y=true_y+ds*$sin(midpoint);
            true_theta=true_theta+dtheta;
            left_travel=$rtoi(vl*0.01*65536.0);right_travel=$rtoi(vr*0.01*65536.0);
            yaw=16'($rtoi(true_theta*65536.0/(2.0*3.141592653589793)));
            travel_tick=1;robot_ticks=robot_ticks+1;
            if(vl!=0.0 || vr!=0.0) move_ticks=move_ticks+1;
            if(robot_ticks%1000==0) begin
                $display("trace t=%0dms true=(%0.1f,%0.1f,%0.1fdeg) estimated=(%0d,%0d,%0d) drive=(%0d,%0d) phase=%0d state=%0d loc=%0d quality=%0d front=%0d replans=%0d",robot_ticks*10,true_x,true_y,true_theta*180.0/3.141592653589793,pose_x,pose_y,pose_heading,drive_left,drive_right,dut.navigation_phase,nav_state,dut.localized,localization_quality,front_distance,dut.replans);$fflush();
            end
        end
    end
    integer n=0;real a,c,s,dx,dy,d,origin_x,origin_y;
    initial forever begin
        @(negedge clk);lidar_point=0;
        if(lidar_valid) begin
            origin_x=true_x+164.0*$cos(true_theta);origin_y=true_y+164.0*$sin(true_theta);
            a=(270-n)*3.141592653589793/180.0+true_theta;c=$cos(a);s=$sin(a);
            dx=c>0.00001 ? (2025.0-origin_x)/c:c< -0.00001 ? (-975.0-origin_x)/c:1000000;
            dy=s>0.00001 ? (1225.0-origin_y)/s:s< -0.00001 ? (-1175.0-origin_y)/s:1000000;d=dx<dy ? dx:dy;
            lidar_angle=n*100;lidar_distance=$rtoi(d+0.5);lidar_point=1;n=(n+1)%360;
        end
        @(negedge clk);lidar_point=0;
        repeat(118) @(negedge clk);
    end
    integer x,y;
    initial begin
        #30;rst_n=1;cmd(8'h50,1);wait(dut.map_ready);
        // Known fixture isolates matching/planning from ray-map quality.
        @(negedge clk);
        for(y=0;y<128;y=y+1) for(x=0;x<128;x=x+1)
            dut.grid.cells[y*128+x]=(x>=44 && x<=104 && y>=40 && y<=88 &&
                (x==44 || x==104 || y==40 || y==88)) ? 2'b10:2'b01;
        cmd(8'h52,0);cmd(8'h53,{176'd0,16'd0,32'd25,32'd25});
        $display("trace synthetic map committed; waiting for localization");$fflush();
        // Skip only the idle post-transfer delay in this accelerated fixture.
        @(negedge clk);dut.transfer_ms=0;lidar_valid=1;
        wait(dut.localized && !dut.matcher_busy && dut.safe_scan);
        $display("trace synthetic localization quality=%0d",localization_quality);$fflush();
        cmd(8'h54,{224'd0,16'd0,8'd64,8'd84});
        wait(!dut.request_nav && dut.localized && !dut.matcher_busy);
        $display("trace synthetic preview complete");$fflush();
        if(!dut.plan_valid || !dut.tracker_ready) $fatal(1,"preview did not produce usable path");
        armed=1;cmd(8'h55,0);
        if(!drive_enabled || drive_left || drive_right) $fatal(1,"planning did not own zero wheel targets");
        wait(dut.nav_running && nav_state==1);
        $display("trace synthetic tracking running");$fflush();
        wait(drive_left>0 && drive_right>0);
        if(drive_left>100 || drive_right>100) $fatal(1,"navigation wheel speed cap");
        wait(mission_arrived || mission_failed);
        if(mission_failed) $fatal(1,"continuous navigation failed fault=%0d state=%0d phase=%0d replans=%0d",nav_fault,nav_state,dut.navigation_phase,dut.replans);
        if(true_x<925.0 || true_x>1125.0 || true_y< -75.0 || true_y>125.0)
            $fatal(1,"actual plant did not reach goal: %0.2f,%0.2f",true_x,true_y);
        if(move_ticks<500) $fatal(1,"arrival fixture did not require substantial travel");
        repeat(20000) @(negedge clk);
        if(drive_enabled || drive_left || drive_right) $fatal(1,"arrival did not release motor ownership");
        $display("PASS continuous ideal plant reaches 1000mm goal true=(%0.2f,%0.2f) ticks=%0d moves=%0d",true_x,true_y,robot_ticks,move_ticks);$finish;
    end
    initial begin #500000000;$fatal(1,"continuous navigation watchdog true=(%0.1f,%0.1f) phase=%0d localized=%0d quality=%0d state=%0d",true_x,true_y,dut.navigation_phase,dut.localized,localization_quality,nav_state);end
endmodule
