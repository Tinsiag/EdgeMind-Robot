`timescale 1ns/1ps
module framebuffer_frame_test_tb;
    parameter FRAME_HEIGHT = 2;
    parameter FULL_PASS_ONLY = 0;
    localparam WIDTH=800, PIXELS=WIDTH*FRAME_HEIGHT, BLOCKS=PIXELS/8;
    localparam TIMEOUT=PIXELS*20+1000;
    reg reset_n=0, wr_clk=0, ui_clk=0, rd_clk=0;
    always #10 wr_clk=~wr_clk;
    always #5 ui_clk=~ui_clk;
    always #15 rd_clk=~rd_clk;
    reg ui_reset=1, calibrated=0, source_valid=0, write_fifo_full=0;
    reg write_fire=0,read_fire=0,read_data_valid=0;
    reg [27:0] command_address=0;
    reg supply_ready=0, inject_error=0, pause_reads=0;
    wire write_enable, input_frame_done,input_overflow,read_enable;
    wire write_frame_done,ui_error,timeout_error,read_pop;
    wire compare_done,compare_error,compare_pass;
    wire [18:0] checked_pixels,first_error_pixel;
    wire [15:0] first_error_expected,first_error_actual;
    integer source_accepted=0, model_pixel=0, rd_cycles=0;
    wire read_fifo_empty=!supply_ready || (pause_reads && (rd_cycles%11<3));
    function [15:0] pattern;
        input integer index;
        integer col,hi,lo;
        begin
            col=index%WIDTH;
            hi=(2*col+1)%256; lo=(2*col+2)%256;
            pattern=hi*256+lo;
        end
    endfunction
    wire [15:0] read_pixel=pattern(model_pixel) ^
        ((inject_error && model_pixel==PIXELS-1) ? 16'h0001 : 16'h0000);
    framebuffer_frame_test #(.FRAME_WIDTH(WIDTH),.FRAME_HEIGHT(FRAME_HEIGHT),
        .UI_TIMEOUT_CYCLES(TIMEOUT)) dut(.*);
    always @(posedge wr_clk) begin
        if(!reset_n)source_accepted<=0;
        else if(write_enable)source_accepted<=source_accepted+1;
    end
    always @(posedge rd_clk) begin
        if(!reset_n)begin model_pixel<=0;rd_cycles<=0;end
        else begin
            rd_cycles<=rd_cycles+1;
            if(read_pop)model_pixel<=model_pixel+1;
        end
    end
    task restart;
        begin
            @(negedge ui_clk);reset_n=0;ui_reset=1;calibrated=0;
            source_valid=0;write_fifo_full=0;write_fire=0;read_fire=0;
            read_data_valid=0;supply_ready=0;inject_error=0;pause_reads=0;
            repeat(6)@(negedge wr_clk);
            reset_n=1;ui_reset=0;calibrated=1;
            repeat(6)@(negedge wr_clk);
            if(compare_pass || compare_error || input_overflow || ui_error || timeout_error)
                $fatal(1,"Reset did not clear flags");
        end
    endtask
    task fill_frame;
        integer i;
        begin
            source_valid=1;
            for(i=0;i<PIXELS+7;i=i+1)@(negedge wr_clk);
            source_valid=0;
            if(source_accepted!=PIXELS || !input_frame_done)
                $fatal(1,"Input limit failed: %0d",source_accepted);
            if(read_enable || read_pop)$fatal(1,"Read before DDR write completion");
            for(i=0;i<BLOCKS;i=i+1)begin
                @(negedge ui_clk);command_address=i*8;write_fire=1;
                @(negedge ui_clk);write_fire=0;
                if(i<BLOCKS-1 && read_enable)$fatal(1,"Premature read enable");
            end
            if(!write_frame_done || !read_enable || ui_error)
                $fatal(1,"Write/address check failed");
        end
    endtask
    task return_frame;
        integer i;
        begin
            for(i=0;i<BLOCKS;i=i+1)begin
                @(negedge ui_clk);command_address=i*8;read_fire=1;
                @(negedge ui_clk);read_fire=0;
            end
            if(read_enable)$fatal(1,"Extra read enabled after frame command count");
            for(i=0;i<BLOCKS;i=i+1)begin
                @(negedge ui_clk);read_data_valid=1;
                @(negedge ui_clk);read_data_valid=0;
            end
            supply_ready=1;
            wait(compare_done);repeat(5)@(negedge rd_clk);
            if(checked_pixels!=PIXELS || model_pixel!=PIXELS || read_pop || ui_error || timeout_error)
                $fatal(1,"Frame length / stop / timeout failed");
        end
    endtask
    initial begin
        restart;fill_frame;pause_reads=1;return_frame;
        if(!compare_pass || compare_error)$fatal(1,"Valid frame did not pass");
        $display("PASS: %0d pixels, FWFT sampling, empty pauses, row/byte wrap, no overrun",PIXELS);
        if(FULL_PASS_ONLY)$finish;
        restart;fill_frame;inject_error=1;return_frame;
        if(compare_pass || !compare_error || first_error_pixel!=PIXELS-1 ||
            first_error_expected!=pattern(PIXELS-1) || first_error_actual!=(pattern(PIXELS-1)^1))
            $fatal(1,"Last pixel corruption was not caught");
        $display("PASS: last-pixel mismatch and first-error record");
        restart;write_fifo_full=1;source_valid=1;
        repeat(2)@(negedge wr_clk);source_valid=0;
        if(!input_overflow || write_enable || source_accepted!=0)
            $fatal(1,"Overflow was not caught");
        $display("PASS: input full blocks write and records overflow");
        restart;
        @(negedge ui_clk);write_fire=1;command_address=8;
        @(negedge ui_clk);write_fire=0;
        if(!ui_error || read_enable)$fatal(1,"Bad write address was not caught");
        $display("PASS: command address sequence failure");
        restart;
        @(negedge ui_clk);read_fire=1;command_address=0;
        @(negedge ui_clk);read_fire=0;
        if(!ui_error)$fatal(1,"Early read was not caught");
        $display("PASS: read-before-write rejected");
        restart;
        @(negedge ui_clk);read_data_valid=1;
        @(negedge ui_clk);read_data_valid=0;
        if(!ui_error)$fatal(1,"Unexpected response was not caught");
        $display("PASS: unsolicited response rejected");
        restart;fill_frame;
        wait(timeout_error);
        #1; // Let the combinational read gate settle after the NBA flag update.
        if(compare_pass || read_enable)$fatal(1,"Timeout incorrectly passed");
        $display("PASS: no-return timeout, no false pass");
        restart;
        $display("All controller tests passed");$finish;
    end
    initial begin #200000000;$fatal(1,"Simulation watchdog");end
endmodule
