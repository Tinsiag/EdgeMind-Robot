`timescale 1ns/1ps
module camera_line_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,enable=1,vsync=1,href=0;reg [7:0] data=0;
    wire pixel_valid;wire [15:0] pixel;wire [10:0] pixel_x,pixel_y;
    wire frame_start,frame_end,frame_good,frame_error,result_valid;
    wire [1:0] regions_valid;wire [10:0] near_center,far_center;wire [15:0] frame_id;
    dvp_capture_continuous #(.WIDTH(32),.HEIGHT(16),.SKIP_FRAMES(1)) capture(.pclk(clk),.rst_n(rst_n),.*);
    line_features #(.WIDTH(32),.HEIGHT(16)) features(.clk(clk),.rst_n(rst_n),.frame_start(frame_start),.frame_end(frame_end),.frame_good(frame_good),.pixel_valid(pixel_valid),.pixel(pixel),.x(pixel_x),.y(pixel_y),.threshold(8'd80),.near_y0(11'd10),.near_y1(11'd13),.far_y0(11'd3),.far_y1(11'd6),.result_valid(result_valid),.regions_valid(regions_valid),.near_center(near_center),.far_center(far_center),.frame_id(frame_id));
    integer xx,yy;integer results=0;
    task frame;
        input integer center,short_line,odd_byte;
        begin
            repeat(5)@(negedge clk);vsync=0;repeat(4)@(negedge clk);
            for(yy=0;yy<16;yy=yy+1) begin
                href=1;
                for(xx=0;xx<(short_line && yy==5 ? 31:32);xx=xx+1) begin
                    data=(xx>=center-2 && xx<=center+2)?0:255;@(negedge clk);
                    data=(xx>=center-2 && xx<=center+2)?0:255;@(negedge clk);
                end
                if(odd_byte && yy==8) begin data=0;@(negedge clk);end
                href=0;repeat(5)@(negedge clk);
            end
            repeat(4)@(negedge clk);vsync=1;
            wait(result_valid);@(negedge clk);results=results+1;
        end
    endtask
    initial begin
        repeat(5)@(negedge clk);rst_n=1;
        frame(16,0,0);if(regions_valid!=0)$fatal(1,"Warm-up frame accepted");
        frame(16,0,0);if(regions_valid!=3 || near_center!=16 || far_center!=16)$fatal(1,"Center extraction failed %d %d %d",regions_valid,near_center,far_center);
        frame(23,0,0);if(regions_valid!=3 || near_center!=23)$fatal(1,"Right line failed");
        frame(8,1,0);if(regions_valid!=0 || !frame_error)$fatal(1,"Short line accepted");
        frame(8,0,1);if(regions_valid!=0 || !frame_error)$fatal(1,"Odd byte accepted");
        frame(8,0,0);if(regions_valid!=3 || near_center!=8)$fatal(1,"Recovery failed");
        frame(90,0,0);if(regions_valid!=0)$fatal(1,"White frame found line");
        $display("PASS: continuous RGB565, warmup, centroids, short/odd frame rejection and recovery");$finish;
    end
    initial begin #300000;$fatal(1,"Watchdog");end
endmodule
