`timescale 1ns/1ps
`default_nettype none
// DDR publishes completed camera frames. HDMI owns the read stream; Ethernet
// consumes a separate lossy copy and can never stall the display or controller.
module a741_video #(parameter WIDTH=800,HEIGHT=480,SKIP_FRAMES=10,NET_FIFO_BITS=13,FUSION_ENABLED=0)(
    input wire clk,rst_n,cam_clk,cam_ready,cam_vsync,cam_href,input wire [7:0] cam_data,
    input wire ui_clk,ui_rst_n,calibrated,pixel_clk,
    output wire [27:0] app_addr,output wire [2:0] app_cmd,output wire app_en,
    input wire app_rdy,output wire [127:0] app_wdf_data,output wire app_wdf_wren,app_wdf_end,
    input wire app_wdf_rdy,input wire [127:0] app_rd_data,input wire app_rd_valid,
    input wire [895:0] snapshot,
    input wire [255:0] fusion_snapshot,
    output wire [15:0] rgb,output wire de,hsync,vsync,
    output wire [7:0] video_data,output wire video_valid,video_last,output wire [15:0] video_length,
    input wire video_ready,
    output wire frame_available,camera_error,ddr_error,overflow,
    output reg [31:0] frames
);
    wire cam_rst,pix_rst,ui_fifo_n;
    reset_sync cam_reset(.clk(cam_clk),.async_n(rst_n),.rst_n(cam_rst));
    reset_sync pix_reset(.clk(pixel_clk),.async_n(rst_n),.rst_n(pix_rst));
    // DDR controller soft reset must not reset only one side of an async FIFO
    // or mailbox. Their pointers/handshakes share the video global reset.
    reset_sync ui_fifo_reset(.clk(ui_clk),.async_n(rst_n),.rst_n(ui_fifo_n));
    wire fs,fe,fg,pv;wire [15:0] cp;
    wire tw,tf,te,tr;wire [17:0] td,tq;
    wire capture_error,capture_overflow;
    dvp_capture_continuous #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.SKIP_FRAMES(SKIP_FRAMES)) capture(.pclk(cam_clk),.rst_n(cam_rst),.enable(cam_ready),.vsync(cam_vsync),.href(cam_href),.data(cam_data),
        .pixel_valid(pv),.pixel(cp),.frame_start(fs),.frame_end(fe),.frame_good(fg),.frame_error(capture_error));
    capture_tokens tokens(.clk(cam_clk),.rst_n(cam_rst),.frame_start(fs),.frame_end(fe),.frame_good(fg),.pixel_valid(pv),.pixel(cp),
        .fifo_full(tf),.fifo_write(tw),.fifo_data(td),.overflow(capture_overflow));
    async_fifo #(.WIDTH(18),.ADDR_BITS(12)) input_fifo(.wr_clk(cam_clk),.wr_rst_n(cam_rst),.wr_en(tw),.wr_data(td),.full(tf),
        .rd_clk(ui_clk),.rd_rst_n(ui_fifo_n),.rd_en(tr && ui_rst_n),.rd_data(tq),.empty(te));
    wire [10:0] x,y;wire blank;
    video_timing #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) timing(.clk(pixel_clk),.rst_n(pix_rst),.de(de),.hsync(hsync),.vsync(vsync),.frame_blank(blank),.x(x),.y(y));
    wire blank_ui,flush_pix,done_ui,flush_ui,done_pix;
    // Event mailboxes keep each CDC handshake atomic. Frame events are >16 ms apart.
    cdc_mailbox #(.WIDTH(1)) bcdc(.src_clk(pixel_clk),.src_rst_n(pix_rst),.src_valid(blank),.src_data(1'b1),
        .src_ready(),.dst_clk(ui_clk),.dst_rst_n(ui_fifo_n),.dst_valid(blank_ui),.dst_data());
    cdc_mailbox #(.WIDTH(1)) fcdc(.src_clk(ui_clk),.src_rst_n(ui_fifo_n),.src_valid(flush_ui),.src_data(1'b1),
        .src_ready(),.dst_clk(pixel_clk),.dst_rst_n(pix_rst),.dst_valid(flush_pix),.dst_data());
    cdc_mailbox #(.WIDTH(1)) dcdc(.src_clk(pixel_clk),.src_rst_n(pix_rst),.src_valid(done_pix),.src_data(1'b1),
        .src_ready(),.dst_clk(ui_clk),.dst_rst_n(ui_fifo_n),.dst_valid(done_ui),.dst_data());
    wire [127:0] display_data,display_q;wire display_push,display_full,display_empty,display_pop;
    wire available_ui,error_ui;wire [31:0] dropped_ui;
    ddr_framebuffer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) framebuffer(.clk(ui_clk),.rst_n(ui_rst_n),.calibrated(calibrated),.source_data(tq),.source_empty(te),.source_pop(tr),
        .display_blank(blank_ui),.display_flush_done(done_ui),.display_flush(flush_ui),
        .display_data(display_data),.display_push(display_push),.display_full(display_full),
        .app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(app_rdy),.app_wdf_data(app_wdf_data),
        .app_wdf_wren(app_wdf_wren),.app_wdf_end(app_wdf_end),.app_wdf_rdy(app_wdf_rdy),
        .app_rd_data(app_rd_data),.app_rd_data_valid(app_rd_valid),
        .frame_available(available_ui),.error(error_ui),.dropped_frames(dropped_ui));
    async_fifo #(.WIDTH(128),.ADDR_BITS(9)) output_fifo(.wr_clk(ui_clk),.wr_rst_n(ui_fifo_n),.wr_en(display_push && ui_rst_n),.wr_data(display_data),.full(display_full),
        .rd_clk(pixel_clk),.rd_rst_n(pix_rst),.rd_en(display_pop),.rd_data(display_q),.empty(display_empty));
    wire [15:0] camera_pixel;wire camera_valid,underrun;
    video_pixels pixels(.clk(pixel_clk),.rst_n(pix_rst),.de(de && av_pix[1]),.frame_blank(blank),.flush(flush_pix),
        .fifo_data(display_q),.fifo_empty(display_empty),.fifo_pop(display_pop),.flush_done(done_pix),
        .pixel(camera_pixel),.pixel_valid(camera_valid),.underrun(underrun));
    wire [895:0] snap_pix;wire [255:0] fusion_pix;wire snap_update;
    cdc_mailbox #(.WIDTH(1152)) osd_cdc(.src_clk(clk),.src_rst_n(rst_n),.src_valid(1'b1),.src_data({fusion_snapshot,snapshot}),
        .src_ready(),.dst_clk(pixel_clk),.dst_rst_n(pix_rst),.dst_valid(snap_update),.dst_data({fusion_pix,snap_pix}));
    a741_osd #(.FUSION_ENABLED(FUSION_ENABLED)) osd(.clk(pixel_clk),.rst_n(pix_rst),.frame_blank(blank),.de(de),.x(x),.y(y),
        .pixel(camera_pixel),.pixel_valid(camera_valid),.status_snapshot(snap_pix),.fusion_snapshot(fusion_pix),.status_update(snap_update),.rgb(rgb));
    // Start marker is in the last blank pixel, avoiding loss of pixel (0,0).
    wire net_start=x==WIDTH+255 && y==HEIGHT+45;
    reg frame_good;reg [31:0] count;
    (* ASYNC_REG="TRUE" *) reg [1:0] av_pix;
    always @(posedge pixel_clk or negedge pix_rst)
        if(!pix_rst) av_pix<=0;else av_pix<={av_pix[0],available_ui};
    always @(posedge pixel_clk or negedge pix_rst)
        if(!pix_rst) begin frame_good<=0;count<=0;end
        else if(net_start) begin frame_good<=1;count<=0;end
        else if(de) begin
            count<=count+1'b1;
            if(av_pix[1] && !camera_valid) frame_good<=0;
        end
    wire nw,nfull,nempty,nread;wire [17:0] nd,nq;wire net_overflow;
    capture_tokens network_tokens(.clk(pixel_clk),.rst_n(pix_rst),.frame_start(net_start),.frame_end(blank),
        .frame_good(frame_good && count==WIDTH*HEIGHT),.pixel_valid(de && !x[0] && !y[0]),.pixel(rgb),
        .fifo_full(nfull),.fifo_write(nw),.fifo_data(nd),.overflow(net_overflow));
    async_fifo #(.WIDTH(18),.ADDR_BITS(NET_FIFO_BITS)) net_fifo(.wr_clk(pixel_clk),.wr_rst_n(pix_rst),.wr_en(nw),.wr_data(nd),.full(nfull),
        .rd_clk(clk),.rd_rst_n(rst_n),.rd_en(nread),.rd_data(nq),.empty(nempty));
    video_udp_packetizer #(.WIDTH(WIDTH/2),.HEIGHT(HEIGHT/2)) packetizer(.clk(clk),.rst_n(rst_n),.token_data(nq),.token_empty(nempty),.token_read(nread),
        .udp_data(video_data),.udp_valid(video_valid),.udp_last(video_last),.udp_length(video_length),.udp_ready(video_ready));
    wire [3:0] diag;wire diag_valid;
    cdc_mailbox #(.WIDTH(4)) diagnostics(.src_clk(pixel_clk),.src_rst_n(pix_rst),.src_valid(1'b1),
        .src_data({net_overflow,underrun,frame_good,1'b0}),.src_ready(),.dst_clk(clk),.dst_rst_n(rst_n),.dst_valid(diag_valid),.dst_data(diag));
    (* ASYNC_REG="TRUE" *) reg [1:0] av_sync,er_sync,ce_sync,co_sync;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin av_sync<=0;er_sync<=0;ce_sync<=0;co_sync<=0;frames<=0;end
        else begin
            av_sync<={av_sync[0],available_ui};er_sync<={er_sync[0],error_ui};
            ce_sync<={ce_sync[0],capture_error};co_sync<={co_sync[0],capture_overflow};
            if(video_valid && video_ready && video_last) frames<=frames+1'b1;
        end
    assign frame_available=av_sync[1];assign ddr_error=er_sync[1] || diag[2];
    assign camera_error=ce_sync[1];assign overflow=co_sync[1] || diag[3];
endmodule
`default_nettype wire
