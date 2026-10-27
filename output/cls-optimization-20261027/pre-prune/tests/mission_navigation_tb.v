`timescale 1ns/1ps
// Real core arbitration, RV32I firmware, room matcher, A*, tracker and local lease.
// Camera/DDR/HDMI pixels, Ethernet video and the TFT run throughout navigation.
// Sensor measurements/ARM are fixture inputs; physical motor validation is separate.
module mission_navigation_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,fixture_armed=0,scan=0,host_pulse=0;
    reg [7:0] host_kind=0;reg [255:0] host_payload=0;
    reg point=0;reg [15:0] angle=0,distance=1000;
    wire [7:0] video_data;wire video_valid,video_last,video_ready;
    wire [15:0] video_length;wire frame_ready,camera_error,ddr_error,video_overflow;
    wire [31:0] video_frames;wire [895:0] snapshot;wire [255:0] fusion_snapshot;
    a741_core #(.CLK_HZ(500000),.FUSION_ENABLED(1),.GEOMETRY_VERIFIED(1),.RADIUS_MM(100),.MOTION_LIDAR(1)) dut(
        .clk(clk),.rst_n(rst_n),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),
        .phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),.eth_tx_ready(1'b1),
        .video_data(video_data),.video_valid(video_valid),.video_last(video_last),.video_length(video_length),.video_ready(video_ready),
        .ddr_ready(rst_n),.frame_ready(frame_ready),.camera_error(camera_error),.ddr_error(ddr_error),
        .video_overflow(video_overflow),.video_frames(video_frames),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot));
    reg ui_clk=0,pixel_clk=0,cam_clk=0;
    always #5 ui_clk=~ui_clk;
    always #15 pixel_clk=~pixel_clk;
    always #20 cam_clk=~cam_clk;
    reg cam_vsync=1,cam_href=0;reg [7:0] cam_data=0;
    wire [27:0] app_addr;wire [2:0] app_cmd;wire app_en,app_wen,app_wend;
    wire [127:0] app_wdata;reg [127:0] app_rdata=0;reg app_rvalid=0;
    wire [15:0] rgb;wire de,hsync,vsync;
    a741_video #(.WIDTH(16),.HEIGHT(8),.SKIP_FRAMES(0),.NET_FIFO_BITS(8),.FUSION_ENABLED(1)) video(
        .clk(clk),.rst_n(rst_n),.cam_clk(cam_clk),.cam_ready(1'b1),.cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),
        .ui_clk(ui_clk),.ui_rst_n(rst_n),.calibrated(rst_n),.pixel_clk(pixel_clk),
        .app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(1'b1),
        .app_wdf_data(app_wdata),.app_wdf_wren(app_wen),.app_wdf_end(app_wend),.app_wdf_rdy(1'b1),
        .app_rd_data(app_rdata),.app_rd_valid(app_rvalid),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot),
        .rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),.video_data(video_data),.video_valid(video_valid),
        .video_last(video_last),.video_length(video_length),.video_ready(video_ready),
        .frame_available(frame_ready),.camera_error(camera_error),.ddr_error(ddr_error),.overflow(video_overflow),.frames(video_frames));
    reg [127:0] camera_memory[0:1023];reg read_pending=0;reg [9:0] read_index;
    wire [9:0] memory_index={app_addr[20],app_addr[11:3]};
    integer ddr_reads=0,camera_pixels=0,video_packets=0,mission_pixels=0;
    always @(posedge ui_clk) begin
        app_rvalid<=read_pending;read_pending<=0;
        if(read_pending) app_rdata<=camera_memory[read_index];
        if(app_en && app_cmd==0 && app_wen) camera_memory[memory_index]<=app_wdata;
        if(app_en && app_cmd==1) begin read_pending<=1;read_index<=memory_index;ddr_reads<=ddr_reads+1;end
    end
    always @(posedge pixel_clk) if(video.camera_valid) begin
        if(video.camera_pixel!==16'hf800) $fatal(1,"camera pixels corrupted during mission");
        camera_pixels<=camera_pixels+1;
        if(dut.fusion_enabled.cpu_owns) mission_pixels<=mission_pixels+1;
    end
    always @(posedge clk) if(video_valid && video_ready && video_last) video_packets<=video_packets+1;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;wire [15:0] tft_rgb;
    integer panel_pixels=0;
    a741_tft480_panel panel(.clk(clk),.rst_n(rst_n),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot),
        .tft_clk(tft_clk),.tft_de(tft_de),.tft_hsync(tft_hsync),.tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
    always @(posedge tft_clk) if(tft_de) panel_pixels<=panel_pixels+1;
    integer cam_row,cam_column;
    initial begin
        wait(rst_n);repeat(10) @(negedge cam_clk);
        forever begin
            cam_vsync=0;repeat(3) @(negedge cam_clk);
            for(cam_row=0;cam_row<8;cam_row=cam_row+1) begin
                for(cam_column=0;cam_column<16;cam_column=cam_column+1) begin
                    @(negedge cam_clk);cam_href=1;cam_data=8'hf8;
                    @(negedge cam_clk);cam_data=0;
                end
                @(negedge cam_clk);cam_href=0;repeat(3) @(negedge cam_clk);
            end
            cam_vsync=1;repeat(1000) @(negedge cam_clk);
        end
    end
    always @(negedge clk) begin
        force dut.iv=1;force dut.gv=1;force dut.yaw=0;force dut.calibrated=1;
        force dut.faults=0;force dut.manual_l=0;force dut.manual_r=0;
        force dut.travel_tick=0;force dut.travel_valid=1;
        force dut.front=1000;force dut.lside=1000;force dut.rside=1000;force dut.lidar_confidence=100;
    end
    // Explicit stimulus events also work in Verilator's procedural-force model.
    always @(host_pulse or host_kind or host_payload or fixture_armed or scan or point or angle or distance) begin
        force dut.fcommand=host_pulse;force dut.fkind=host_kind;force dut.fpayload=host_payload;
        force dut.armed=fixture_armed;force dut.lv=scan;
        force dut.lidar_point=point;force dut.lidar_angle=angle;force dut.lidar_distance=distance;
    end
    integer goals=0,starts=0;
    always @(posedge clk) if(rst_n && dut.fusion_enabled.mission_progress[31:24]!=0)
        $fatal(1,"integrated task failed progress=%h phase=%0d nav=%0d",dut.fusion_enabled.mission_progress,dut.fusion_enabled.autonomy.navigation_phase,dut.nav_state);
    always @(posedge clk) if(dut.fusion_enabled.cpu_command) begin
        $display("trace core CPU nav command=%h progress=%h",dut.fusion_enabled.cpu_kind,dut.fusion_enabled.mission_progress);$fflush();
        if(dut.fusion_enabled.cpu_kind==8'h54) begin
            if(dut.fusion_enabled.cpu_payload[7:0]!=63+goals || dut.fusion_enabled.cpu_payload[15:8]!=64)
                $fatal(1,"core changed mission goal order");
            goals<=goals+1;
        end
        if(dut.fusion_enabled.cpu_kind==8'h55) starts<=starts+1;
    end
    task cmd(input [7:0] k,input [255:0] p,input integer expected);
        integer age;
        begin
            @(negedge clk);host_kind=k;host_payload=p;host_pulse=1;
            @(negedge clk);host_pulse=0;age=0;
            while(!dut.freply_valid && age<200000) begin @(negedge clk);age=age+1;end
            if(!dut.freply_valid || dut.freply[7:0]!=expected)
                $fatal(1,"core host reply kind=%h code=%d expected=%d armed=%0d imu=%0d cal=%0d request=%0d match=%0d",k,dut.freply[7:0],expected,
                    dut.armed,dut.iv,dut.calibrated,dut.fusion_enabled.autonomy.request_nav,dut.fusion_enabled.autonomy.matcher_busy);
            @(negedge clk);
        end
    endtask
    integer n=0;real a,c,s,dx,dy,d;
    initial forever begin
        @(negedge clk);point=0;
        if(scan) begin
            a=(270-n)*3.141592653589793/180.0;c=$cos(a);s=$sin(a);
            dx=c>0.00001 ? 1010/c:c< -0.00001 ? -990/c:1000000;
            dy=s>0.00001 ? 1210/s:s< -0.00001 ? -1190/s:1000000;d=dx<dy ? dx:dy;
            angle=n*100;distance=$rtoi(d+0.5);point=1;n=(n+1)%360;
        end
        @(negedge clk);point=0;repeat(118) @(negedge clk);
    end
    integer x,y;
    initial begin
        #30;rst_n=1;cmd(8'h50,1,0);wait(dut.fusion_enabled.autonomy.map_ready);
        @(negedge clk);
        for(y=0;y<128;y=y+1) for(x=0;x<128;x=x+1)
            dut.fusion_enabled.autonomy.grid.cells[y*128+x]=(x>=44 && x<=84 && y>=40 && y<=88 &&
                (x==44 || x==84 || y==40 || y==88)) ? 2'b10:2'b01;
        cmd(8'h52,0,0);cmd(8'h53,{176'd0,16'd0,32'd25,32'd25},0);
        $display("trace integrated room map ready");$fflush();
        @(negedge clk);dut.fusion_enabled.autonomy.transfer_ms=0;scan=1;
        wait(dut.fusion_enabled.autonomy.localized && !dut.fusion_enabled.autonomy.matcher_busy && dut.fusion_enabled.autonomy.safe_scan);
        $display("trace integrated room localized");$fflush();
        cmd(8'h58,0,0);cmd(8'h58,{216'd0,32'h0000403f,8'd1},0);
        cmd(8'h58,{216'd0,32'h00004040,8'd1},0);cmd(8'h58,{216'd0,32'h00004041,8'd1},0);
        fixture_armed=1;cmd(8'h58,2,0);wait(dut.mission_alive);
        // External TTL is expired throughout the mission; no host heartbeat.
        force dut.motion.command_age=1000;
        cmd(8'h50,0,2); // Active mission must reject external map changes.
        wait(starts==3);wait(!dut.fusion_enabled.cpu_owns);repeat(3000) @(negedge clk);
        if(goals!=3 || dut.fusion_enabled.mission_progress[7:0]!=3 || dut.fusion_enabled.mission_progress[31:24]!=0 ||
           dut.fusion_enabled.cpu_fault || dut.fusion_enabled.autonomy_owns || dut.fstop)
            $fatal(1,"integrated completion failed goals=%0d starts=%0d progress=%h",goals,starts,dut.fusion_enabled.mission_progress);
        if(!frame_ready || camera_error || ddr_error || ddr_reads<16 || camera_pixels<128 || video_packets==0 || panel_pixels==0 || mission_pixels==0)
            $fatal(1,"parallel video missing/broken: ready=%0d camera_error=%0d ddr_error=%0d reads=%0d pixels=%0d packets=%0d panel=%0d mission_pixels=%0d",
                frame_ready,camera_error,ddr_error,ddr_reads,camera_pixels,video_packets,panel_pixels,mission_pixels);
        $display("PASS real core RV32I to room-localized A*/tracker, three nearby waypoints, expired host TTL, active map rejection and concurrent camera/DDR/HDMI pixels/Ethernet/TFT");$finish;
    end
    initial begin #120000000;$fatal(1,"integrated mission watchdog progress=%h nav=%0d pose=%0d,%0d tracker=%0d,%0d remaining=%0d arrived=%0d running=%0d req=%0d",
        dut.fusion_enabled.mission_progress,dut.nav_state,dut.pose_x,dut.pose_y,
        dut.fusion_enabled.autonomy.tracker.current_x,dut.fusion_enabled.autonomy.tracker.current_y,
        dut.fusion_enabled.autonomy.tracker.remaining,dut.fusion_enabled.autonomy.arrived,
        dut.fusion_enabled.autonomy.nav_running,dut.fusion_enabled.autonomy.request_nav);end
endmodule
