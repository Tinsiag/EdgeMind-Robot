`timescale 1ns/1ps
// Synthetic 3x2.4m room with the compiled CAD footprint/offset.
// Static pose fixture checks localization, stop/replan and resumed steering;
// it does not simulate continuous vehicle dynamics or physical arrival accuracy.
module cad_navigation_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;integer cycles=0;
    wire ms_tick=cycles%500==499,tick=cycles%5000==4999;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;
    always @(posedge clk) if(dut.match_result) begin
        $display("trace match accepted=%0d localized=%0d quality=%0d scan=%0d coverage=%h points=%0d front=%0d rear=%0d overflow=%0d",dut.match_accepted,dut.localized,localization_quality,dut.safe_scan,dut.safety.coverage,dut.safety.points,front_distance,dut.rear_distance,dut.project_overflow);$fflush();
    end
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
    integer n=0;reg inject_obstacle=0;real a,c,s,dx,dy,d;
    // A full room revolution every 86.4 simulated milliseconds.
    initial forever begin
        @(negedge clk);lidar_point=0;
        if(lidar_valid) begin
            a=(270-n)*3.141592653589793/180.0;c=$cos(a);s=$sin(a);
            dx=c>0.00001 ? 1846/c:c< -0.00001 ? -1154/c:1000000;
            dy=s>0.00001 ? 1210/s:s< -0.00001 ? -1190/s:1000000;d=dx<dy ? dx:dy;
            lidar_angle=n*100;lidar_distance=inject_obstacle && n>=268 && n<=272 ? 286:$rtoi(d+0.5);lidar_point=1;n=(n+1)%360;
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
        inject_obstacle=1;
        wait(dut.request_nav && dut.navigation_phase==7);@(negedge clk);#1;
        if(drive_left || drive_right || !drive_enabled || force_stop) $fatal(1,"obstacle did not pause for bounded replan");
        inject_obstacle=0;
        wait(!dut.request_nav && dut.nav_running && nav_state==1);
        wait(drive_left!=0 || drive_right!=0);
        if(dut.replans!=1) $fatal(1,"unexpected replan attempts");
        link_alive=0;@(negedge clk);#1;
        if(drive_left || drive_right) $fatal(1,"link loss retained navigation wheel targets");
        repeat(3) @(negedge clk);link_alive=1;repeat(30) @(negedge clk);
        if(drive_enabled || drive_left || drive_right || !dut.guard_locked) $fatal(1,"link restoration auto-restarted navigation");
        $display("PASS synthetic room localization, preview, stationary planning, obstacle pause/replan/resume and link-loss latch");$finish;
    end
    initial begin #250000000;$fatal(1,"synthetic navigation watchdog phase=%0d localized=%0d quality=%0d state=%0d",dut.navigation_phase,dut.localized,localization_quality,nav_state);end
endmodule
