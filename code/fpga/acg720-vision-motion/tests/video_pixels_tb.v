`timescale 1ns/1ps
module video_pixels_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,de=0,frame_blank=0,flush=0;
    wire [127:0] fifo_data;reg fifo_empty=1;wire fifo_pop,flush_done;
    wire [15:0] pixel;wire pixel_valid;wire underrun;
    video_pixels dut(.*);
    integer i,k,word=0,seen=0;
    genvar n;
    generate for(n=0;n<8;n=n+1)begin: pixels
        assign fifo_data[n*16+:16]=word*8+n;
    end endgenerate
    always @(posedge clk)if(rst_n)begin
        if(fifo_pop && !dut.draining)word<=word+1;
        if(de && pixel_valid)begin if(pixel!==seen)$fatal(1,"Pixel gap/order: expected %d got %d",seen,pixel);seen<=seen+1;end
    end
    initial begin
        repeat(4)@(negedge clk);rst_n=1;flush=1;@(negedge clk);flush=0;
        wait(flush_done);@(negedge clk);fifo_empty=0;
        repeat(3)@(negedge clk);de=1;
        repeat(32)@(negedge clk);de=0;
        if(seen!=32 || underrun)$fatal(1,"Unpacker drops a pixel between blocks %d",seen);
        fifo_empty=1;de=1;repeat(20)@(negedge clk);de=0;
        if(!underrun)$fatal(1,"Underrun unreported");
        frame_blank=1;@(negedge clk);frame_blank=0;flush=1;@(negedge clk);flush=0;
        wait(flush_done);@(negedge clk);if(dut.failed)$fatal(1,"Next-frame recovery failed");
        $display("PASS: gap-free 128-to-16 unpack, underrun detection and next-blank recovery");$finish;
    end
    initial begin #20000;$fatal(1,"Watchdog");end
endmodule
