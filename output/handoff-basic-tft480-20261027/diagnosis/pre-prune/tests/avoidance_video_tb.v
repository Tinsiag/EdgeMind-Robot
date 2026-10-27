`timescale 1ns/1ps
// Basic core, bare supervisor and avoidance with concurrent video and TFT.
// Camera/DDR/HDMI pixels, Ethernet video and the TFT run throughout navigation.
// Sensor measurements/ARM are fixture inputs; physical motor validation is separate.
module avoidance_video_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,fixture_armed=0,scan=1,host_pulse=0;
    reg [15:0] front=1000,left=1000,right=1000;
    reg [7:0] rx_data=0;reg rx_valid=0,rx_last=0;wire rx_ready;
    reg [7:0] host_kind=0;reg [255:0] host_payload=0;
    reg point=0;reg [15:0] angle=0,distance=1000;
    wire [7:0] video_data;wire video_valid,video_last,video_ready;
    wire [15:0] video_length;wire frame_ready,camera_error,ddr_error,video_overflow;
    wire [31:0] video_frames;wire [895:0] snapshot;wire [255:0] fusion_snapshot;
    a741_core #(.CLK_HZ(500000),.FUSION_ENABLED(1),.GEOMETRY_VERIFIED(1),.RADIUS_MM(257),.LIDAR_X(164),.MOTION_LIDAR(1)) dut(
        .clk(clk),.rst_n(rst_n),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),
        .phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),
        .eth_rx_data(rx_data),.eth_rx_valid(rx_valid),.eth_rx_last(rx_last),.eth_rx_bad(1'b0),.eth_rx_ready(rx_ready),.eth_tx_ready(1'b1),
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
    a741_video #(.WIDTH(16),.HEIGHT(8),.SKIP_FRAMES(0),.NET_FIFO_BITS(8),.FUSION_ENABLED(1),.TFT_V3_ENABLED(1)) video(
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
        if(dut.fowns) mission_pixels<=mission_pixels+1;
    end
    always @(posedge clk) if(video_valid && video_ready && video_last) video_packets<=video_packets+1;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;wire [15:0] tft_rgb;
    integer panel_pixels=0;
    a741_tft800_panel panel(.pixel_clk(pixel_clk),.rst_n(rst_n),.rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),
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
        force dut.front=front;force dut.lside=left;force dut.rside=right;force dut.motion.command_age=0;force dut.lidar_confidence=100;
    end
    // Explicit stimulus events also work in Verilator's procedural-force model.
    always @(host_pulse or host_kind or host_payload or fixture_armed or scan or point or angle or distance) begin
        force dut.fcommand=host_pulse;force dut.fkind=host_kind;force dut.fpayload=host_payload;
        force dut.armed=fixture_armed;force dut.lv=scan;
        force dut.lidar_point=point;force dut.lidar_angle=angle;force dut.lidar_distance=distance;
    end
    integer ethernet_index=0,ethernet_video_frames=0;reg [15:0] udp_destination=0;
    always @(posedge clk) if(dut.eth_tx_valid) begin
        if(ethernet_index==36) udp_destination[15:8]<=dut.eth_tx_data;
        if(ethernet_index==37) udp_destination[7:0]<=dut.eth_tx_data;
        if(dut.eth_tx_last) begin
            if(udp_destination==6102) ethernet_video_frames<=ethernet_video_frames+1;
            ethernet_index<=0;
        end else ethernet_index<=ethernet_index+1;
    end
    task arp_peer;
        reg [335:0] packet;integer n;
        begin
            packet={48'h020000000002,48'h020000000003,16'h0806,16'h0001,16'h0800,8'd6,8'd4,16'd2,
                48'h020000000003,32'hc0a80003,48'h020000000002,32'hc0a80002};
            for(n=0;n<42;n=n+1) begin
                @(negedge clk);rx_data=packet[335-n*8-:8];rx_valid=1;rx_last=n==41;
                @(posedge clk);while(!rx_ready) @(posedge clk);
            end
            @(negedge clk);rx_valid=0;rx_last=0;
        end
    endtask
    task cmd(input [7:0] k,input [255:0] p);
        integer age;
        begin
            @(negedge clk);host_kind=k;host_payload=p;host_pulse=1;
            @(negedge clk);host_pulse=0;age=0;
            while(!dut.freply_valid && age<2000) begin @(negedge clk);age=age+1;end
            if(!dut.freply_valid || dut.freply[7:0]) $fatal(1,"parallel control reply %h",k);
            @(negedge clk);
        end
    endtask
    integer before_packets;
    initial begin
        #30;rst_n=1;repeat(5000) @(negedge clk);arp_peer();fixture_armed=1;cmd(8'h59,1);
        if(!dut.fowns || dut.fl!=120 || dut.fr!=120) $fatal(1,"parallel cruise did not start");
        repeat(900000) @(negedge clk);before_packets=ethernet_video_frames;
        front=300;left=800;right=550;repeat(1000) @(negedge clk);
        if(dut.fl!=-80 || dut.fr!=80) $fatal(1,"parallel turn did not start");
        repeat(100000) @(negedge clk);
        if(ethernet_video_frames<=before_packets) $fatal(1,"video stalled while turning");
        scan=0;repeat(8) @(negedge clk);
        if(dut.fl || dut.fr || !dut.fobstacle) $fatal(1,"lidar loss did not stop targets");
        before_packets=ethernet_video_frames;repeat(100000) @(negedge clk);
        if(ethernet_video_frames<=before_packets) $fatal(1,"video stalled while blocked");
        cmd(8'h59,0);repeat(1000) @(negedge clk);
        if(dut.fowns || dut.fl || dut.fr) $fatal(1,"parallel stop retained targets");
        if(!frame_ready || camera_error || ddr_error || ddr_reads<16 || camera_pixels<128 ||
            video_packets==0 || panel_pixels==0 || mission_pixels==0 || !dut.fusion_enabled.cpu_alive)
            $fatal(1,"parallel pipeline missing camera=%0d pixels=%0d packets=%0d panel=%0d",frame_ready,camera_pixels,ethernet_video_frames,panel_pixels);
        $display("PASS basic avoidance cruise/turn/lidar-stop with real CPU, camera/DDR/HDMI pixels, actual Ethernet UDP video and TFT");$finish;
    end
    initial begin #30000000;$fatal(1,"basic parallel watchdog");end
endmodule
