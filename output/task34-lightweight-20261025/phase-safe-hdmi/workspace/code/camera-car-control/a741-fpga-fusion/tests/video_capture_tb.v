`timescale 1ns/1ps
module video_capture_tb;
    reg pclk=0;always #5 pclk=~pclk;
    reg rst_n=0,enable=1,vsync=1,href=0;reg [7:0] data=0;
    wire pixel_valid,frame_start,frame_end,frame_good,frame_error;
    wire [15:0] pixel;wire [10:0] pixel_x,pixel_y;
    dvp_capture_continuous #(.WIDTH(16),.HEIGHT(8),.SKIP_FRAMES(2)) dut(.*);
    task frame(input integer extra_pixels);
        integer row,column,count;
        begin
            @(negedge pclk);vsync=0;repeat(3) @(negedge pclk);
            for(row=0;row<8;row=row+1) begin
                count=16+(row==0 ? extra_pixels:0);
                for(column=0;column<count;column=column+1) begin
                    href=1;data=8'hf8;@(negedge pclk);data=0;@(negedge pclk);
                end
                href=0;repeat(3) @(negedge pclk);
            end
            vsync=1;repeat(3) @(negedge pclk);
        end
    endtask
    initial begin
        #30;rst_n=1;
        frame(0);if(frame_good || frame_error) $fatal(1,"first warmup frame");
        frame(0);if(frame_good || frame_error) $fatal(1,"second warmup frame");
        frame(0);if(!frame_good || frame_error || dut.skipped!=2) $fatal(1,"valid frame after warmup");
        frame(256);
        if(frame_good || !frame_error || dut.pixels!=129) $fatal(1,"long frame overflow not retained");
        frame(0);if(!frame_good || frame_error) $fatal(1,"valid frame did not recover");
        enable=0;repeat(3) @(negedge pclk);enable=1;
        frame(0);if(frame_good || frame_error || dut.skipped!=1) $fatal(1,"disable did not restart warmup");
        $display("PASS bounded capture counters, warmup, malformed long-frame saturation and recovery");$finish;
    end
    initial begin #100000;$fatal(1,"capture watchdog");end
endmodule
