`timescale 1ns/1ps
`default_nettype none
// Portable integration boundary. Clocks, camera initialization, DDR PHY and
// TMDS output belong to the explicitly supplied board-support platform.
module vision_motion_top #(parameter CLK_HZ=50000000,WIDTH=800,HEIGHT=480,SKIP_FRAMES=10)(
    input wire clk50,ui_clk,pixel_clk,async_reset_n,camera_init_done,ddr_calibrated,
    input wire uart_rx,output wire uart_tx,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,
    input wire camera_pclk,camera_vsync,camera_href,input wire [7:0] camera_data,
    inout wire tof_sda,tof_scl,tof_xshut,
    output wire [27:0] app_addr,output wire [2:0] app_cmd,output wire app_en,
    input wire app_rdy,output wire [127:0] app_wdf_data,
    output wire app_wdf_wren,app_wdf_end,output wire [15:0] app_wdf_mask,
    input wire app_wdf_rdy,input wire [127:0] app_rd_data,input wire app_rd_data_valid,
    output wire [15:0] video_rgb,output reg video_de,video_hsync,video_vsync,
    output wire [7:0] led
);
    wire r50,rcam,rui,rpix;
    reset_sync rr0(.clk(clk50),.async_n(async_reset_n),.rst_n(r50));
    reset_sync rr1(.clk(camera_pclk),.async_n(async_reset_n),.rst_n(rcam));
    reset_sync rr2(.clk(ui_clk),.async_n(async_reset_n),.rst_n(rui));
    reset_sync rr3(.clk(pixel_clk),.async_n(async_reset_n),.rst_n(rpix));
    (* ASYNC_REG="TRUE" *) reg [1:0] cam_enable;
    always @(posedge camera_pclk or negedge rcam)
        if(!rcam) cam_enable<=0;else cam_enable<={cam_enable[0],camera_init_done && ddr_calibrated};
    wire pv,fs,fe,fg,ferr;wire [15:0] cp;wire [10:0] cx,cy;
    dvp_capture_continuous #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.SKIP_FRAMES(SKIP_FRAMES)) capture(.pclk(camera_pclk),.rst_n(rcam),.enable(cam_enable[1]),.vsync(camera_vsync),.href(camera_href),.data(camera_data),.pixel_valid(pv),.pixel(cp),.pixel_x(cx),.pixel_y(cy),.frame_start(fs),.frame_end(fe),.frame_good(fg),.frame_error(ferr));
    wire [7:0] threshold;wire [10:0] ny0,ny1,fy0,fy1;
    wire [51:0] cfg_in={threshold,ny0,ny1,fy0,fy1};
    wire cfg_ready,cfg_valid;wire [51:0] cfg_cam;
    reg [51:0] cfg_pending,cfg_active;
    cdc_mailbox #(.WIDTH(52)) cfg(.src_clk(clk50),.src_rst_n(r50),.src_valid(cfg_ready),.src_data(cfg_in),.src_ready(cfg_ready),.dst_clk(camera_pclk),.dst_rst_n(rcam),.dst_valid(cfg_valid),.dst_data(cfg_cam));
    always @(posedge camera_pclk or negedge rcam)
        if(!rcam) begin cfg_pending<={8'd80,11'd360,11'd399,11'd260,11'd299};cfg_active<={8'd80,11'd360,11'd399,11'd260,11'd299};end
        else begin if(cfg_valid) cfg_pending<=cfg_cam;if(fs) cfg_active<=cfg_pending;end
    wire features_update;wire [1:0] regions;wire [10:0] nc,fc;wire [15:0] frame_id;
    line_features #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) features(.clk(camera_pclk),.rst_n(rcam),.frame_start(fs),.frame_end(fe),.frame_good(fg),.pixel_valid(pv),.pixel(cp),.x(cx),.y(cy),.threshold(cfg_active[51:44]),.near_y0(cfg_active[43:33]),.near_y1(cfg_active[32:22]),.far_y0(cfg_active[21:11]),.far_y1(cfg_active[10:0]),.result_valid(features_update),.regions_valid(regions),.near_center(nc),.far_center(fc),.frame_id(frame_id));
    wire line_update;wire [39:0] line_data;wire line_ready;
    cdc_mailbox #(.WIDTH(40)) feature_cdc(.src_clk(camera_pclk),.src_rst_n(rcam),.src_valid(features_update),.src_data({frame_id,regions,fc,nc}),.src_ready(line_ready),.dst_clk(clk50),.dst_rst_n(r50),.dst_valid(line_update),.dst_data(line_data));
    wire token_write,token_full,token_empty,token_pop,overflow;
    wire [17:0] token_data,source_data;
    capture_tokens tokens(.clk(camera_pclk),.rst_n(rcam),.frame_start(fs),.frame_end(fe),.frame_good(fg),.pixel_valid(pv),.pixel(cp),.fifo_full(token_full),.fifo_write(token_write),.fifo_data(token_data),.overflow(overflow));
    async_fifo #(.WIDTH(18),.ADDR_BITS(12)) capture_fifo(.wr_clk(camera_pclk),.wr_rst_n(rcam),.wr_en(token_write),.wr_data(token_data),.full(token_full),.rd_clk(ui_clk),.rd_rst_n(rui),.rd_en(token_pop),.rd_data(source_data),.empty(token_empty));
    wire de,hs,vs,blank;wire [10:0] vx,vy;
    video_timing #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) timing(.clk(pixel_clk),.rst_n(rpix),.de(de),.hsync(hs),.vsync(vs),.frame_blank(blank),.x(vx),.y(vy));
    wire blank_ui,blank_ready,flush_ui,flush_pixel,flush_ready,flush_done_pixel,flush_done_ui,done_ready;
    wire unused0,unused1,unused2;
    cdc_mailbox #(.WIDTH(1)) blank_cdc(.src_clk(pixel_clk),.src_rst_n(rpix),.src_valid(blank),.src_data(1'b1),.src_ready(blank_ready),.dst_clk(ui_clk),.dst_rst_n(rui),.dst_valid(blank_ui),.dst_data(unused0));
    cdc_mailbox #(.WIDTH(1)) flush_cdc(.src_clk(ui_clk),.src_rst_n(rui),.src_valid(flush_ui),.src_data(1'b1),.src_ready(flush_ready),.dst_clk(pixel_clk),.dst_rst_n(rpix),.dst_valid(flush_pixel),.dst_data(unused1));
    cdc_mailbox #(.WIDTH(1)) flushed_cdc(.src_clk(pixel_clk),.src_rst_n(rpix),.src_valid(flush_done_pixel),.src_data(1'b1),.src_ready(done_ready),.dst_clk(ui_clk),.dst_rst_n(rui),.dst_valid(flush_done_ui),.dst_data(unused2));
    wire [127:0] video_block,read_block;wire block_push,block_full,block_pop,block_empty;
    wire available,ddr_error,read_bank,write_bank;wire [31:0] dropped;
    ddr_framebuffer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) fb(.clk(ui_clk),.rst_n(rui),.calibrated(ddr_calibrated),.source_data(source_data),.source_empty(token_empty),.source_pop(token_pop),.display_blank(blank_ui),.display_flush_done(flush_done_ui),.display_flush(flush_ui),.display_data(video_block),.display_push(block_push),.display_full(block_full),.app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(app_rdy),.app_wdf_data(app_wdf_data),.app_wdf_wren(app_wdf_wren),.app_wdf_end(app_wdf_end),.app_wdf_rdy(app_wdf_rdy),.app_rd_data(app_rd_data),.app_rd_data_valid(app_rd_data_valid),.frame_available(available),.error(ddr_error),.dropped_frames(dropped),.read_bank(read_bank),.write_bank(write_bank));
    assign app_wdf_mask=0;
    async_fifo #(.WIDTH(128),.ADDR_BITS(6)) display_fifo(.wr_clk(ui_clk),.wr_rst_n(rui),.wr_en(block_push),.wr_data(video_block),.full(block_full),.rd_clk(pixel_clk),.rd_rst_n(rpix),.rd_en(block_pop),.rd_data(read_block),.empty(block_empty));
    wire [15:0] display_pixel;wire display_valid,underrun;
    video_pixels unpack(.clk(pixel_clk),.rst_n(rpix),.de(de),.frame_blank(blank),.flush(flush_pixel),.fifo_data(read_block),.fifo_empty(block_empty),.fifo_pop(block_pop),.flush_done(flush_done_pixel),.pixel(display_pixel),.pixel_valid(display_valid),.underrun(underrun));
    // Display underrun is reported, but doesn't poison the independent control
    // path forever. A DDR protocol error does inhibit autonomous motion.
    (* ASYNC_REG="TRUE" *) reg [1:0] av50,err50,und50,of50;
    always @(posedge clk50 or negedge r50)
        if(!r50) begin av50<=0;err50<=0;und50<=0;of50<=0;end
        else begin av50<={av50[0],available};err50<={err50[0],ddr_error};und50<={und50[0],underrun};of50<={of50[0],overflow};end
    wire ms_tick,xi,xr,xb,xd,xe,xshut_low;
    wire [15:0] xreg,tof_distance;wire [2:0] xn;wire [31:0] xwrite,xdata;
    wire tof_init,tof_error,tof_update,tof_valid;wire [7:0] range_status;
    assign tof_xshut=xshut_low ? 1'b0:1'bz;
    i2c_reg_master #(.CLK_HZ(CLK_HZ)) i2c(.clk(clk50),.rst_n(r50),.start(xi),.read(xr),.address(7'h29),.reg_addr(xreg),.byte_count(xn),.write_data(xwrite),.read_data(xdata),.busy(xb),.done(xd),.error(xe),.sda(tof_sda),.scl(tof_scl));
    vl53l1x_driver tof(.clk(clk50),.rst_n(r50),.ms_tick(ms_tick),.xshut_low(xshut_low),.xfer_start(xi),.xfer_read(xr),.xfer_reg(xreg),.xfer_count(xn),.xfer_write(xwrite),.xfer_busy(xb),.xfer_done(xd),.xfer_error(xe),.xfer_data(xdata),.init_done(tof_init),.error(tof_error),.sample_update(tof_update),.sample_valid(tof_valid),.distance_mm(tof_distance),.range_status(range_status));
    wire [191:0] osd50,osdp;wire osd_ready,osd_update;
    vision_motion_control #(.CLK_HZ(CLK_HZ)) control(.clk(clk50),.rst_n(r50),.uart_rx(uart_rx),.uart_tx(uart_tx),.left_a(left_enc_a),.left_b(left_enc_b),.right_a(right_enc_a),.right_b(right_enc_b),.line_update(line_update),.regions_valid(line_data[23:22]),.near_center(line_data[10:0]),.far_center(line_data[21:11]),.line_frame_id(line_data[39:24]),.tof_update(tof_update),.tof_valid(tof_valid),.tof_error(tof_error),.distance_mm(tof_distance),.range_status(range_status),.video_ready(av50[1]),.video_error(err50[1]),.video_warning({of50[1],und50[1]}),.left_in1(left_in1),.left_in2(left_in2),.right_in1(right_in1),.right_in2(right_in2),.threshold(threshold),.near_y0(ny0),.near_y1(ny1),.far_y0(fy0),.far_y1(fy1),.osd_status(osd50),.led(led),.ms_tick(ms_tick));
    cdc_mailbox #(.WIDTH(192)) osd_cdc(.src_clk(clk50),.src_rst_n(r50),.src_valid(ms_tick),.src_data(osd50),.src_ready(osd_ready),.dst_clk(pixel_clk),.dst_rst_n(rpix),.dst_valid(osd_update),.dst_data(osdp));
    wire [15:0] osd_rgb;
    video_osd osd(.clk(pixel_clk),.rst_n(rpix),.frame_blank(blank),.de(de),.x(vx),.y(vy),.camera_pixel(display_pixel),.camera_valid(display_valid),.status_snapshot(osdp),.status_update(osd_update),.rgb(osd_rgb));
    reg [15:0] rgb_q;
    always @(posedge pixel_clk or negedge rpix)
        if(!rpix) begin rgb_q<=0;video_de<=0;video_hsync<=1;video_vsync<=1;end
        else begin rgb_q<=osd_rgb;video_de<=de;video_hsync<=hs;video_vsync<=vs;end
    assign video_rgb=rgb_q;
endmodule
`default_nettype wire
