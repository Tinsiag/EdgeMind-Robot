`timescale 1ns/1ps
module video_tb;
    reg clk=0,ui=0,pclk=0,cam=0;always #10 clk=~clk;always #5 ui=~ui;
    always #15 pclk=~pclk;always #20 cam=~cam;
    reg rst=0,vs=1,href=0,ready=0;reg [7:0] cd=0;
    wire [27:0] addr;wire [2:0] cmd;wire en,wen,wend;
    wire [127:0] wd;reg [127:0] rd=0;reg rv=0;
    wire [15:0] rgb,vlen;wire de,vv,vl,available,ce,derr,overflow;
    wire [7:0] vd;wire [31:0] frames;
    a741_video #(.WIDTH(16),.HEIGHT(8),.SKIP_FRAMES(0),.NET_FIFO_BITS(4)) dut(
        .clk(clk),.rst_n(rst),.cam_clk(cam),.cam_ready(1'b1),.cam_vsync(vs),.cam_href(href),.cam_data(cd),
        .ui_clk(ui),.ui_rst_n(rst),.calibrated(rst),.pixel_clk(pclk),
        .app_addr(addr),.app_cmd(cmd),.app_en(en),.app_rdy(1'b1),.app_wdf_data(wd),.app_wdf_wren(wen),.app_wdf_end(wend),.app_wdf_rdy(1'b1),
        .app_rd_data(rd),.app_rd_valid(rv),.snapshot(896'd0),
        .rgb(rgb),.de(de),.hsync(),.vsync(),.video_data(vd),.video_valid(vv),.video_last(vl),.video_length(vlen),.video_ready(ready),
        .frame_available(available),.camera_error(ce),.ddr_error(derr),.overflow(overflow),.frames(frames));
    reg [127:0] memory[0:1023];reg pending=0;reg [9:0] read_index;
    integer reads=0,shown=0,packets=0,row,x;
    wire [9:0] mem_index={addr[20],addr[11:3]};
    always @(posedge ui) begin
        rv<=pending;pending<=0;
        if(pending) rd<=memory[read_index];
        if(en && cmd==0 && wen) memory[mem_index]<=wd;
        if(en && cmd==1) begin pending<=1;read_index<=mem_index;reads=reads+1;end
    end
    always @(posedge pclk) if(dut.camera_valid) begin
        if(dut.camera_pixel!=16'hf800) $fatal(1,"DDR pixel corruption");
        shown=shown+1;
    end
    always @(posedge clk) if(vv && ready && vl) packets=packets+1;
    initial begin
        #200;rst=1;
        #1000000;
        if(derr || available) $fatal(1,"camera warmup falsely reported display underrun");
        repeat(10) @(negedge cam);vs=0;repeat(3) @(negedge cam);
        for(row=0;row<8;row=row+1) begin
            for(x=0;x<16;x=x+1) begin @(negedge cam);href=1;cd=8'hf8;@(negedge cam);cd=0;end
            @(negedge cam);href=0;repeat(3) @(negedge cam);
        end
        vs=1;
        #1100000;
        if(!available || reads<16 || shown<128 || !overflow) $fatal(1,"HDMI stalled under Ethernet congestion %d %d",reads,shown);
        ready=1;#1000000;
        if(packets==0 || shown<256 || derr || ce) $fatal(1,"display/network recovery %d %d %d %d",packets,shown,derr,ce);
        $display("PASS camera full-frame DDR, HDMI independent of network stall, video drop and recovery");$finish;
    end
    initial begin #5000000;$fatal(1,"watchdog");end
endmodule
