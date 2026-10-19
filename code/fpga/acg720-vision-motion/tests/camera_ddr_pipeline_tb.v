`timescale 1ns/1ps
// Real DVP bytes -> capture -> token FIFO -> DDR interface -> output FIFO ->
// pixel unpack. Independent clocks and separate command/data backpressure.
module camera_ddr_pipeline_tb #(parameter W=32,H=16);
    localparam PIXELS=W*H,BLOCKS=PIXELS/8;
    reg cam_clk=0,ui_clk=0,pix_clk=0;
    always #11 cam_clk=~cam_clk;always #5 ui_clk=~ui_clk;always #15 pix_clk=~pix_clk;
    reg rst_n=0,vsync=1,href=0;reg [7:0] data=0;
    wire pv,fs,fe,fg,ferr;wire [15:0] pixel;wire [10:0] x,y;
    dvp_capture_continuous #(.WIDTH(W),.HEIGHT(H),.SKIP_FRAMES(0)) capture(.pclk(cam_clk),.rst_n(rst_n),.enable(1'b1),.vsync(vsync),.href(href),.data(data),.pixel_valid(pv),.pixel(pixel),.pixel_x(x),.pixel_y(y),.frame_start(fs),.frame_end(fe),.frame_good(fg),.frame_error(ferr));
    wire tw,full,overflow;wire [17:0] td,sd;wire empty,pop;
    capture_tokens tokens(.clk(cam_clk),.rst_n(rst_n),.frame_start(fs),.frame_end(fe),.frame_good(fg),.pixel_valid(pv),.pixel(pixel),.fifo_full(full),.fifo_write(tw),.fifo_data(td),.overflow(overflow));
    async_fifo #(.WIDTH(18),.ADDR_BITS(8)) input_fifo(.wr_clk(cam_clk),.wr_rst_n(rst_n),.wr_en(tw),.wr_data(td),.full(full),.rd_clk(ui_clk),.rd_rst_n(rst_n),.rd_en(pop),.rd_data(sd),.empty(empty));
    reg display_blank=0;wire flush_ui,flush_pixel,done_ui,done_pixel;wire cr0,cr1;wire unused0,unused1;
    cdc_mailbox #(.WIDTH(1)) req(.src_clk(ui_clk),.src_rst_n(rst_n),.src_valid(flush_ui),.src_data(1'b1),.src_ready(cr0),.dst_clk(pix_clk),.dst_rst_n(rst_n),.dst_valid(flush_pixel),.dst_data(unused0));
    cdc_mailbox #(.WIDTH(1)) ack(.src_clk(pix_clk),.src_rst_n(rst_n),.src_valid(done_pixel),.src_data(1'b1),.src_ready(cr1),.dst_clk(ui_clk),.dst_rst_n(rst_n),.dst_valid(done_ui),.dst_data(unused1));
    wire [127:0] block,rd;wire push,out_full,out_empty,out_pop;
    wire [27:0] app_addr;wire [2:0] app_cmd;wire app_en,app_wdf_wren,app_wdf_end;
    wire [127:0] app_wdf_data;reg app_rdy=0,app_wdf_rdy=0;reg [127:0] app_rd_data=0;reg app_rd_data_valid=0;
    wire available,error,read_bank,write_bank;wire [31:0] dropped;
    ddr_framebuffer #(.WIDTH(W),.HEIGHT(H)) fb(.clk(ui_clk),.rst_n(rst_n),.calibrated(1'b1),.source_data(sd),.source_empty(empty),.source_pop(pop),.display_blank(display_blank),.display_flush_done(done_ui),.display_flush(flush_ui),.display_data(block),.display_push(push),.display_full(out_full),.app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(app_rdy),.app_wdf_data(app_wdf_data),.app_wdf_wren(app_wdf_wren),.app_wdf_end(app_wdf_end),.app_wdf_rdy(app_wdf_rdy),.app_rd_data(app_rd_data),.app_rd_data_valid(app_rd_data_valid),.frame_available(available),.error(error),.dropped_frames(dropped),.read_bank(read_bank),.write_bank(write_bank));
    async_fifo #(.WIDTH(128),.ADDR_BITS(4)) output_fifo(.wr_clk(ui_clk),.wr_rst_n(rst_n),.wr_en(push),.wr_data(block),.full(out_full),.rd_clk(pix_clk),.rd_rst_n(rst_n),.rd_en(out_pop),.rd_data(rd),.empty(out_empty));
    reg de=0;wire [15:0] display_pixel;wire valid,underrun;
    video_pixels video(.clk(pix_clk),.rst_n(rst_n),.de(de),.frame_blank(1'b0),.flush(flush_pixel),.fifo_data(rd),.fifo_empty(out_empty),.fifo_pop(out_pop),.flush_done(done_pixel),.pixel(display_pixel),.pixel_valid(valid),.underrun(underrun));
    reg [127:0] memory[0:BLOCKS*2-1],saved_data;reg [27:0] saved_address,read_address;
    reg cmd_seen=0,data_seen=0;integer latency=0,cycle=0,seen=0,expected_base=0;
    always @(negedge ui_clk)begin cycle=cycle+1;app_rdy=cycle%4!=0;app_wdf_rdy=cycle%3!=0;end
    always @(posedge ui_clk)begin
        app_rd_data_valid<=0;
        if(rst_n)begin
            if(app_en && app_rdy && app_cmd==0)begin
                if(available && app_addr[20]==read_bank)$fatal(1,"Display bank overwritten");
                saved_address=app_addr;cmd_seen=1;
            end
            if(app_wdf_wren && app_wdf_rdy)begin saved_data=app_wdf_data;data_seen=1;end
            if(cmd_seen && data_seen)begin memory[(saved_address[20]?BLOCKS:0)+((saved_address & 28'hfffff)>>3)]=saved_data;cmd_seen=0;data_seen=0;end
            if(app_en && app_rdy && app_cmd==1)begin read_address=app_addr;latency=3;end
            if(latency>0)begin latency=latency-1;if(latency==0)begin app_rd_data<=memory[(read_address[20]?BLOCKS:0)+((read_address & 28'hfffff)>>3)];app_rd_data_valid<=1;end end
        end
    end
    always @(posedge pix_clk)if(rst_n && de)begin
        if(!valid)$fatal(1,"Pixel FIFO underrun at %d",seen);
        if(display_pixel!==((expected_base+seen)&65535))$fatal(1,"End-to-end pixel mismatch %d %d",seen,display_pixel);
        seen=seen+1;
    end
    integer xx,yy;reg [15:0] p;
    task frame;input integer offset;begin
        repeat(5)@(negedge cam_clk);vsync=0;repeat(5)@(negedge cam_clk);
        for(yy=0;yy<H;yy=yy+1)begin
            href=1;
            for(xx=0;xx<W;xx=xx+1)begin p=offset+yy*W+xx;data=p[15:8];@(negedge cam_clk);data=p[7:0];@(negedge cam_clk);end
            href=0;repeat(5)@(negedge cam_clk);
        end
        vsync=1;
        wait(fb.pending_frame);repeat(8)@(negedge ui_clk);
    end endtask
    task show;input integer offset;begin
        expected_base=offset;seen=0;
        @(negedge ui_clk);display_blank=1;@(negedge ui_clk);display_blank=0;
        wait(done_ui);repeat(100)@(negedge pix_clk);de=1;
        repeat(PIXELS)@(negedge pix_clk);de=0;
        if(seen!=PIXELS || error || overflow || underrun)$fatal(1,"Pipeline flags/count");
    end endtask
    initial begin
        #100;rst_n=1;frame(0);show(0);frame(1000);show(1000);
        $display("PASS: two complete %dx%d camera frames cross independent FIFO/DDR/display domains without tearing or pixel loss",W,H);$finish;
    end
    initial begin #200000000;$fatal(1,"Pipeline watchdog");end
endmodule
