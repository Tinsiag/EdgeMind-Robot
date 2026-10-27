`timescale 1ns/1ps
// Full 480x272 DVP -> DDR double buffer -> TFT + attitude text, while the
// real RV32 supervisor and basic avoidance run. Sensor/ARM stimulus is injected;
// physical sensor, DDR calibration, motor and final timing remain board tests.
module camera_tft_tb;
 reg clk=0;always #10 clk=~clk;
 reg ui_clk=0;always #5 ui_clk=~ui_clk;
 reg cam_clk=0;always #25 cam_clk=~cam_clk;
 reg rst_n=0,cam_vsync=1,cam_href=0;reg [7:0] cam_data=0;
 wire [27:0] app_addr;wire [2:0] app_cmd;wire app_en,app_wen,app_wend;
 wire [127:0] app_wdata;reg [127:0] app_rdata=0;reg app_rvalid=0;
 integer cycles=0;
 always @(posedge ui_clk) cycles<=cycles+1;
 wire app_rdy=(cycles%11)!=0,app_wrdy=(cycles%7)!=0;
 wire pixel_request,frame_blank,active,tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;
 wire [10:0] x,y;wire [15:0] pixel,rgb,tft_rgb;wire pixel_valid,available,camera_error,ddr_error,overflow;
 wire [31:0] frames;wire [895:0] snapshot;wire [255:0] fusion_snapshot;
 a741_video #(.SKIP_FRAMES(0)) video(.clk(clk),.rst_n(rst_n),.cam_clk(cam_clk),.cam_ready(1'b1),
  .cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(cam_data),.ui_clk(ui_clk),.ui_rst_n(rst_n),.calibrated(rst_n),
  .pixel_request(pixel_request),.frame_blank(frame_blank),.app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),
  .app_rdy(app_rdy),.app_wdf_data(app_wdata),.app_wdf_wren(app_wen),.app_wdf_end(app_wend),.app_wdf_rdy(app_wrdy),
  .app_rd_data(app_rdata),.app_rd_valid(app_rvalid),.pixel(pixel),.pixel_valid(pixel_valid),
  .frame_available(available),.camera_error(camera_error),.ddr_error(ddr_error),.overflow(overflow),.frames(frames));
 a741_osd overlay(.clk(clk),.rst_n(rst_n),.frame_blank(frame_blank),.de(active),.x(x),.y(y),
  .pixel(pixel),.pixel_valid(pixel_valid),.status_snapshot(snapshot),.status_update(1'b1),.fusion_snapshot(fusion_snapshot),.rgb(rgb));
 a741_tft480_panel #(.BACKLIGHT_FRAMES(1)) panel(.*);
 reg [127:0] memory[0:32767];
 wire [14:0] word_index={app_addr[20],app_addr[16:3]};
 reg have_cmd=0,have_data=0;reg [14:0] write_index,read_index;reg [127:0] write_data;
 reg [3:0] read_wait=0;
 wire take_cmd=app_en && app_rdy && app_cmd==0;
 wire take_data=app_wen && app_wrdy;
 integer writes=0,reads=0;
 always @(posedge ui_clk) begin
  app_rvalid<=0;
  if(take_cmd) begin have_cmd<=1;write_index<=word_index;end
  if(take_data) begin have_data<=1;write_data<=app_wdata;end
  if((have_cmd || take_cmd) && (have_data || take_data)) begin
   memory[take_cmd ? word_index:write_index]<=take_data ? app_wdata:write_data;
   have_cmd<=0;have_data<=0;writes<=writes+1;
  end
  if(app_en && app_rdy && app_cmd==1) begin
   if(read_wait!=0) $fatal(1,"multiple DDR read requests without credit");
   read_index<=word_index;read_wait<=3;reads<=reads+1;
  end else if(read_wait!=0) begin
   read_wait<=read_wait-1'b1;
   if(read_wait==1) begin app_rdata<=memory[read_index];app_rvalid<=1;end
  end
 end
 function [15:0] image_pixel;
  input integer px,py;input tag;
  begin image_pixel={tag,4'(px),6'(py),5'(px^py)};end
 endfunction
 integer row,column,source_frame=0;reg [15:0] source_pixel;
 initial begin
  wait(rst_n);repeat(10) @(negedge cam_clk);
  forever begin
   cam_vsync=0;repeat(3) @(negedge cam_clk);
   for(row=0;row<272;row=row+1) begin
    for(column=0;column<480;column=column+1) begin
     source_pixel=image_pixel(column,row,source_frame[0]);
     @(negedge cam_clk);cam_href=1;cam_data=source_pixel[15:8];
     @(negedge cam_clk);cam_data=source_pixel[7:0];
    end
    @(negedge cam_clk);cam_href=0;repeat(8) @(negedge cam_clk);
   end
   cam_vsync=1;source_frame=source_frame+1;repeat(300) @(negedge cam_clk);
  end
 end
 reg armed=0,scan=1,host_command=0;reg [7:0] host_kind=0;reg [255:0] host_payload=0;
 reg [15:0] front=1000,left=1000,right=1000;
 a741_core #(.CLK_HZ(500000),.FUSION_ENABLED(1),.MOTION_LIDAR(1),.GEOMETRY_VERIFIED(1),.RADIUS_MM(257),.LIDAR_X(164)) core(
  .clk(clk),.rst_n(rst_n),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),.phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
  .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),.eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),.eth_tx_ready(1'b1),
  .ddr_ready(available),.frame_ready(available),.camera_error(camera_error),.ddr_error(ddr_error),.video_overflow(overflow),.video_frames(frames),
  .snapshot(snapshot),.fusion_snapshot(fusion_snapshot));
 always @(negedge clk) begin
  force core.tilt_valid=1;force core.iv=1;force core.gv=1;force core.yaw=-16'sd16384;force core.roll=16'sd8192;force core.pitch=-16'sd4096;
  force core.calibrated=1;force core.faults=0;force core.manual_l=0;force core.manual_r=0;force core.motion.command_age=0;
 end
 always @(armed or scan or host_command or host_kind or host_payload or front or left or right) begin
  force core.armed=armed;force core.lv=scan;force core.front=front;force core.lside=left;force core.rside=right;
  force core.fcommand=host_command;force core.fkind=host_kind;force core.fpayload=host_payload;
 end
 task command(input [7:0] kind,input [255:0] payload);
  begin @(negedge clk);host_kind=kind;host_payload=payload;host_command=1;@(negedge clk);host_command=0;end
 endtask
 integer scan_frames=0,correct_pixels=0,text_pixels=0;reg [10:0] px,py;reg check_pixel,tag_seen,tag;
 wire in_text=x>=48 && x<432 && ((y>=8 && y<40)||(y>=232 && y<264));
 reg selected_text;
 always @(posedge clk) if(rst_n) begin
  if(pixel_request) begin
   px=x;py=y;selected_text=in_text;check_pixel=scan_frames>=1;
   if(check_pixel && !pixel_valid) $fatal(1,"DDR/TFT underrun at %0d,%0d frame%0d",x,y,scan_frames);
  end
  if(frame_blank) begin scan_frames=scan_frames+1;tag_seen=0;end
 end
 integer frame_file=0;reg [15:0] expected_color;
 initial begin
  frame_file=$fopen(".local/tests/camera-tft.ppm","wb");$fwrite(frame_file,"P6\n480 272\n255\n");
 end
 always @(posedge tft_clk) if(rst_n && tft_de && check_pixel) begin
  if(!selected_text) begin
   expected_color=image_pixel(px,py,1'b0);
   if(tft_rgb[14:0]!==expected_color[14:0]) $fatal(1,"camera pixel mismatch xy=%0d,%0d got=%h",px,py,tft_rgb);
   if(tag_seen && tft_rgb[15]!==tag) $fatal(1,"DDR frame tore between banks");
   tag=tft_rgb[15];tag_seen=1;correct_pixels=correct_pixels+1;
  end else if(tft_rgb==16'hffff) text_pixels=text_pixels+1;
  if(scan_frames==2 && frame_file) $fwrite(frame_file,"%c%c%c",{tft_rgb[15:11],3'd0},{tft_rgb[10:5],2'd0},{tft_rgb[4:0],3'd0});
 end
 initial begin
  #50;rst_n=1;repeat(5000) @(negedge clk);armed=1;command(8'h59,1);repeat(1000) @(negedge clk);
  if(!core.fowns || core.fl!=120 || core.fr!=120) $fatal(1,"cruise start");
  wait(scan_frames==2);front=300;left=800;right=550;repeat(1000) @(negedge clk);
  if(core.fl!=-80 || core.fr!=80) $fatal(1,"avoidance turn while displaying");
  wait(scan_frames==3);scan=0;repeat(20) @(negedge clk);
  if(core.fl || core.fr || !core.fobstacle) $fatal(1,"lidar loss stop");
  command(8'h59,0);repeat(20) @(negedge clk);
  if(core.fowns || !core.basic_enabled.cpu_alive || correct_pixels<180000 || text_pixels<100 || writes<16320 || reads<16320 || camera_error || ddr_error || overflow)
   $fatal(1,"parallel health pixels=%0d text=%0d writes=%0d reads=%0d camera=%b ddr=%b overflow=%b",correct_pixels,text_pixels,writes,reads,camera_error,ddr_error,overflow);
  $fclose(frame_file);
  $display("PASS full camera480x272 -> DDR with command/data stalls -> TFT RGB+attitude overlay; frame coherence; real CPU+avoidance cruise/turn/lidar stop; no Ethernet video");$finish;
 end
 initial begin #150000000;$fatal(1,"camera/TFT integration watchdog");end
endmodule
