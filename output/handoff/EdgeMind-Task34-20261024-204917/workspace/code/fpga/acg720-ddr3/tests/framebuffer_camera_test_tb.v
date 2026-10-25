`timescale 1ns/1ps
module framebuffer_camera_test_tb;
    parameter FRAME_HEIGHT=2;
    parameter FULL_PASS_ONLY=0;
    localparam WIDTH=800, PIXELS=WIDTH*FRAME_HEIGHT, BLOCKS=PIXELS/8;
    reg reset_n=0, test_reset_n=0, pclk=0, ui_clk=0, rd_clk=0;
    always #11 pclk=~pclk;
    always #5 ui_clk=~ui_clk;
    always #15 rd_clk=~rd_clk;
    reg vsync=1, href=0, ready=0;
    reg [7:0] data=0;
    wire dv, hs, vs;
    wire [15:0] pixel;
    DVP_Capture dvp(.Rst_n(reset_n), .PCLK(pclk), .Vsync(vsync),
      .Href(href), .Data(data), .ImageState(), .DataValid(dv), .DataPixel(pixel),
      .DataHs(hs), .DataVs(vs), .Xaddr(), .Yaddr());
    wire source_valid,capture_done,capture_good,geometry_error;
    wire [18:0] frame_pixels;
    wire [11:0] line_pixels;
    wire [10:0] frame_lines;
    camera_frame_gate #(.FRAME_WIDTH(WIDTH),.FRAME_HEIGHT(FRAME_HEIGHT)) gate(
      .clk(pclk), .reset_n(test_reset_n), .ready(ready), .frame_active(vs),
      .line_active(hs), .pixel_valid(dv), .source_valid(source_valid),
      .frame_done(capture_done), .frame_good(capture_good),
      .geometry_error(geometry_error), .frame_pixels(frame_pixels),
      .line_pixels(line_pixels), .frame_lines(frame_lines));
    reg ui_reset=1, calibrated=0, write_fifo_full=0;
    reg write_fire=0, read_fire=0, read_data_valid=0;
    reg [27:0] command_address=0;
    reg supply_ready=0, corrupt=0;
    integer accepted=0, consumed=0, rd_cycles=0;
    reg [15:0] memory[0:PIXELS-1];
    wire empty=!supply_ready || rd_cycles%13<3;
    wire [15:0] read_pixel=memory[consumed] ^
        ((corrupt && consumed==PIXELS-1) ? 16'h0001 : 16'h0000);
    wire write_enable,input_frame_done,input_overflow,read_enable;
    wire write_frame_done,ui_error,timeout_error,read_pop;
    wire compare_done,compare_error,compare_pass;
    wire [18:0] checked_pixels, first_error_pixel;
    wire [15:0] first_error_expected, first_error_actual;
    wire [31:0] source_crc,read_crc;
    framebuffer_camera_test #(.FRAME_WIDTH(WIDTH),.FRAME_HEIGHT(FRAME_HEIGHT),
      .UI_TIMEOUT_CYCLES(PIXELS*60+100000)) dut(
      .reset_n(test_reset_n),.wr_clk(pclk),.ui_clk(ui_clk),.rd_clk(rd_clk),
      .ui_reset(ui_reset),.calibrated(calibrated),.source_valid(source_valid),
      .source_pixel(pixel),.capture_good(capture_good),.source_crc(source_crc),.read_crc(read_crc),
      .write_fifo_full(write_fifo_full),.write_enable(write_enable),
      .input_frame_done(input_frame_done),.input_overflow(input_overflow),
      .write_fire(write_fire),.read_fire(read_fire),.command_address(command_address),
      .read_data_valid(read_data_valid),.read_enable(read_enable),.write_frame_done(write_frame_done),
      .ui_error(ui_error),.timeout_error(timeout_error),.read_fifo_empty(empty),.read_pixel(read_pixel),
      .read_pop(read_pop),.compare_done(compare_done),.compare_error(compare_error),
      .compare_pass(compare_pass),.checked_pixels(checked_pixels),.first_error_pixel(first_error_pixel),
      .first_error_expected(first_error_expected),.first_error_actual(first_error_actual));
    function [15:0] pattern;
      input integer index;
      begin pattern=(index*13+(index>>7)) & 65535; end
    endfunction
    always @(posedge pclk) begin
      if(!test_reset_n) accepted<=0;
      else if(write_enable) begin
        if(pixel!==pattern(accepted))$fatal(1,"Official DVP packing error at %0d: %h",accepted,pixel);
        memory[accepted]<=pixel; accepted<=accepted+1;
      end
    end
    always @(posedge rd_clk) begin
      if(!test_reset_n)begin consumed<=0;rd_cycles<=0;end
      else begin
        rd_cycles<=rd_cycles+1;
        if(read_pop)consumed<=consumed+1;
      end
    end
    task restart;
      integer n;
      begin
        @(negedge pclk);reset_n=0;test_reset_n=0;ready=0;vsync=1;href=0;
        calibrated=0;ui_reset=1;write_fire=0;read_fire=0;read_data_valid=0;
        supply_ready=0;corrupt=0;write_fifo_full=0;
        repeat(5)@(negedge pclk);
        reset_n=1;calibrated=1;ui_reset=0;
        // Only sync pulses are needed to exercise the official ten-frame discard.
        for(n=0;n<12;n=n+1)begin
          vsync=1;repeat(7)@(negedge pclk);
          vsync=0;repeat(7)@(negedge pclk);
        end
        // Hold the test in reset during empty warmup frames, then select the
        // first complete data frame after a known blanking interval.
        vsync=1;
        repeat(5)@(negedge pclk);
        test_reset_n=1;ready=1;
        repeat(5)@(negedge pclk);
      end
    endtask
    task emit_frame;
      input integer bad_line;
      integer y,x,line_width;
      reg [15:0] value;
      begin
        vsync=0;repeat(6)@(negedge pclk);
        for(y=0;y<FRAME_HEIGHT;y=y+1)begin
          line_width=(y==bad_line) ? WIDTH-1 : WIDTH;
          href=1;
          for(x=0;x<line_width;x=x+1)begin
            value=pattern(y*WIDTH+x);
            data=value[15:8];@(negedge pclk);
            data=value[7:0];@(negedge pclk);
          end
          href=0;repeat(6)@(negedge pclk);
        end
        if(bad_line<0 && read_enable)$fatal(1,"Read before full frame boundary");
        vsync=1;repeat(7)@(negedge pclk);
      end
    endtask
    task roundtrip;
      integer i;
      begin
        if(!capture_good || geometry_error || accepted!=PIXELS || !input_frame_done)
          $fatal(1,"Frame geometry / input count wrong: %0d/%0d, flags %b %b",frame_pixels,frame_lines,capture_good,geometry_error);
        if(source_crc !== (FRAME_HEIGHT==480 ? 32'hcc8b28ab : 32'h5e8bd936))
          $fatal(1,"Source CRC disagrees with Python zlib golden: %h",source_crc);
        for(i=0;i<BLOCKS;i=i+1)begin
          @(negedge ui_clk);command_address=i*8;write_fire=1;
          @(negedge ui_clk);write_fire=0;
        end
        repeat(4)@(negedge ui_clk);
        if(!read_enable)$fatal(1,"Read not enabled for completed valid frame");
        for(i=0;i<BLOCKS;i=i+1)begin
          @(negedge ui_clk);command_address=i*8;read_fire=1;
          @(negedge ui_clk);read_fire=0;read_data_valid=1;
          @(negedge ui_clk);read_data_valid=0;
        end
        supply_ready=1;
        wait(compare_done);repeat(5)@(negedge rd_clk);
        if(ui_error || timeout_error || checked_pixels!=PIXELS || read_pop)
          $fatal(1,"UI counts / exact read limit / timeout failed");
      end
    endtask
    initial begin
      restart;emit_frame(-1);roundtrip;
      if(!compare_pass || compare_error || read_crc!==source_crc)$fatal(1,"Valid CRC did not pass");
      $display("PASS: official DVP -> complete %0d-pixel frame, CRC32/zlib golden, asynchronous clocks, FWFT pauses",PIXELS);
      if(FULL_PASS_ONLY)$finish;
      restart;emit_frame(-1);corrupt=1;roundtrip;
      if(compare_pass || !compare_error || read_crc===source_crc)$fatal(1,"Corrupt last pixel was accepted");
      $display("PASS: corrupted DDR-return pixel fails CRC comparison");
      restart;emit_frame(FRAME_HEIGHT-1);
      if(capture_good || !geometry_error || read_enable)$fatal(1,"Short camera line accepted");
      $display("PASS: short line cannot trigger DDR readback/pass");
      restart;write_fifo_full=1;emit_frame(-1);
      if(!input_overflow || input_frame_done || compare_pass)$fatal(1,"FIFO overflow accepted");
      $display("PASS: FIFO overflow prevents complete input/pass");
      $finish;
    end
    initial begin #100000000; $fatal(1,"Testbench watchdog"); end
endmodule
