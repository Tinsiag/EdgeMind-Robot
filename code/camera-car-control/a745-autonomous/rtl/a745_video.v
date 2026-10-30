`timescale 1ns/1ps
`default_nettype none
// Camera -> complete DDR double buffers -> pixel consumer in its own clk domain.
// The board supplies the real 33MHz display PLL; legacy benches use a strobe.
// Ethernet has no connection to this pixel pipeline.
module a745_video #(parameter WIDTH=480,HEIGHT=272,SKIP_FRAMES=10,INPUT_FIFO_BITS=12)(
 input wire clk,rst_n,cam_clk,cam_ready,cam_vsync,cam_href,input wire [7:0] cam_data,
 input wire ui_clk,ui_rst_n,calibrated,
 input wire pixel_request,frame_blank,
 output wire [27:0] app_addr,output wire [2:0] app_cmd,output wire app_en,
 input wire app_rdy,output wire [127:0] app_wdf_data,output wire app_wdf_wren,app_wdf_end,
 input wire app_wdf_rdy,input wire [127:0] app_rd_data,input wire app_rd_valid,
 output wire [15:0] pixel,output wire pixel_valid,
 output wire frame_available,camera_error,ddr_error,overflow,
 output reg [31:0] frames
);
 wire cam_rst,ui_fifo_n;
 reset_sync cam_reset(.clk(cam_clk),.async_n(rst_n),.rst_n(cam_rst));
 reset_sync ui_fifo_reset(.clk(ui_clk),.async_n(rst_n),.rst_n(ui_fifo_n));
 wire fs,fe,fg,pv;wire [15:0] cp;
 wire tw,tf,te,tr;wire [17:0] td,tq;
 wire capture_error,capture_overflow;
 a745_dvp_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.SKIP_FRAMES(SKIP_FRAMES)) capture(
  .pclk(cam_clk),.rst_n(cam_rst),.enable(cam_ready),.vsync(cam_vsync),.href(cam_href),.data(cam_data),
  .pixel_valid(pv),.pixel(cp),.frame_start(fs),.frame_end(fe),.frame_good(fg),.frame_error(capture_error));
 capture_tokens tokens(.clk(cam_clk),.rst_n(cam_rst),.frame_start(fs),.frame_end(fe),.frame_good(fg),
  .pixel_valid(pv),.pixel(cp),.fifo_full(tf),.fifo_write(tw),.fifo_data(td),.overflow(capture_overflow));
 async_fifo #(.WIDTH(18),.ADDR_BITS(INPUT_FIFO_BITS)) input_fifo(
  .wr_clk(cam_clk),.wr_rst_n(cam_rst),.wr_en(tw),.wr_data(td),.full(tf),
  .rd_clk(ui_clk),.rd_rst_n(ui_fifo_n),.rd_en(tr && ui_rst_n),.rd_data(tq),.empty(te));
 wire blank_ui,flush_ui,flush_sys,done_sys,done_ui;
 cdc_mailbox #(.WIDTH(1)) bcdc(.src_clk(clk),.src_rst_n(rst_n),.src_valid(frame_blank),.src_data(1'b1),
  .src_ready(),.dst_clk(ui_clk),.dst_rst_n(ui_fifo_n),.dst_valid(blank_ui),.dst_data());
 cdc_mailbox #(.WIDTH(1)) fcdc(.src_clk(ui_clk),.src_rst_n(ui_fifo_n),.src_valid(flush_ui),.src_data(1'b1),
  .src_ready(),.dst_clk(clk),.dst_rst_n(rst_n),.dst_valid(flush_sys),.dst_data());
 cdc_mailbox #(.WIDTH(1)) dcdc(.src_clk(clk),.src_rst_n(rst_n),.src_valid(done_sys),.src_data(1'b1),
  .src_ready(),.dst_clk(ui_clk),.dst_rst_n(ui_fifo_n),.dst_valid(done_ui),.dst_data());
 wire [127:0] display_data,display_q;wire display_push,display_full,display_empty,display_pop;
 wire available_ui,error_ui;wire [31:0] dropped_ui;
 ddr_framebuffer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) framebuffer(.clk(ui_clk),.rst_n(ui_rst_n),.calibrated(calibrated),
  .source_data(tq),.source_empty(te),.source_pop(tr),.display_blank(blank_ui),.display_flush_done(done_ui),
  .display_flush(flush_ui),.display_data(display_data),.display_push(display_push),.display_full(display_full),
  .app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(app_rdy),.app_wdf_data(app_wdf_data),
  .app_wdf_wren(app_wdf_wren),.app_wdf_end(app_wdf_end),.app_wdf_rdy(app_wdf_rdy),
  .app_rd_data(app_rd_data),.app_rd_data_valid(app_rd_valid),
  .frame_available(available_ui),.error(error_ui),.dropped_frames(dropped_ui));
 async_fifo #(.WIDTH(128),.ADDR_BITS(6)) output_fifo(
  .wr_clk(ui_clk),.wr_rst_n(ui_fifo_n),.wr_en(display_push && ui_rst_n),.wr_data(display_data),.full(display_full),
  .rd_clk(clk),.rd_rst_n(rst_n),.rd_en(display_pop),.rd_data(display_q),.empty(display_empty));
 wire underrun;
 video_pixels pixels(.clk(clk),.rst_n(rst_n),.de(pixel_request && av_sync[1]),.frame_blank(frame_blank),.flush(flush_sys),
  .fifo_data(display_q),.fifo_empty(display_empty),.fifo_pop(display_pop),.flush_done(done_sys),
  .pixel(pixel),.pixel_valid(pixel_valid),.underrun(underrun));
 (* ASYNC_REG="TRUE" *) reg [1:0] av_sync,er_sync,ce_sync,co_sync;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin av_sync<=0;er_sync<=0;ce_sync<=0;co_sync<=0;frames<=0;end
  else begin
   av_sync<={av_sync[0],available_ui};er_sync<={er_sync[0],error_ui};
   ce_sync<={ce_sync[0],capture_error};co_sync<={co_sync[0],capture_overflow};
   if(frame_blank && av_sync[1]) frames<=frames+1'b1;
  end
 assign frame_available=av_sync[1];assign ddr_error=er_sync[1] || underrun;
 assign camera_error=ce_sync[1];assign overflow=co_sync[1];
endmodule
`default_nettype wire
