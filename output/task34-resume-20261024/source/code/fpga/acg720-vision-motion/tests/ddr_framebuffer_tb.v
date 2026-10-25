`timescale 1ns/1ps
module ddr_framebuffer_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,calibrated=1;
    reg [17:0] source_data=0;reg source_empty=1;wire source_pop;
    reg display_blank=0,display_flush_done=0;wire display_flush;
    wire [127:0] display_data;wire display_push;reg display_full=0;
    wire [27:0] app_addr;wire [2:0] app_cmd;wire app_en;
    reg app_rdy=0,app_wdf_rdy=0;wire [127:0] app_wdf_data;wire app_wdf_wren,app_wdf_end;
    reg [127:0] app_rd_data=0;reg app_rd_data_valid=0;
    wire frame_available,error,read_bank,write_bank;wire [31:0] dropped_frames;
    ddr_framebuffer #(.WIDTH(16),.HEIGHT(2)) dut(.*);
    reg [127:0] memory[0:15],saved_data;reg [27:0] saved_address;reg cmd_seen=0,data_seen=0;
    integer cycle=0,committed=0,returned=0,latency=0;reg [27:0] read_address;
    integer bank_index,word_index,i;reg [127:0] expected;reg contiguous=0;
    always @(negedge clk) begin
        cycle=cycle+1;app_rdy=cycle%3!=0;app_wdf_rdy=cycle%5==0;
    end
    always @(posedge clk)begin
        app_rd_data_valid<=0;
        if(rst_n)begin
            if(app_en && app_rdy && app_cmd==0)begin
                if(frame_available && app_addr[20]==read_bank)$fatal(1,"Write overwrote displayed bank");
                saved_address=app_addr;cmd_seen=1;
            end
            if(app_wdf_wren && app_wdf_rdy)begin saved_data=app_wdf_data;data_seen=1;end
            if(cmd_seen && data_seen)begin
                memory[(saved_address[20]?8:0)+saved_address[5:3]]=saved_data;
                committed=committed+1;cmd_seen=0;data_seen=0;
            end
            if(app_en && app_rdy && app_cmd==1)begin
                if(latency!=0)$fatal(1,"Multiple unreserved reads");read_address=app_addr;latency=4;
            end
            if(latency>0)begin
                latency=latency-1;
                if(latency==0)begin app_rd_data<=memory[(read_address[20]?8:0)+read_address[5:3]];app_rd_data_valid<=1;end
            end
            if(display_push)begin
                if(display_data[15:0]!==returned*8)$fatal(1,"Frame read pixel mismatch %h",display_data);
                returned=returned+1;
            end
        end
    end
    task token;input [17:0] t;begin
        @(negedge clk);source_empty=0;source_data=t;
        do @(posedge clk);while(!source_pop);
        if(!contiguous) begin @(negedge clk);source_empty=1;end
    end endtask
    task frame;input integer good;begin
        token({2'b01,16'd0});
        for(i=0;i<32;i=i+1)token({2'b00,16'(i)});
        token({good?2'b10:2'b11,16'd0});
        @(negedge clk);source_empty=1;
    end endtask
    task blank;begin
        @(negedge clk);display_blank=1;@(negedge clk);display_blank=0;
        wait(display_flush);@(negedge clk);repeat(8)@(negedge clk);
        display_flush_done=1;@(negedge clk);display_flush_done=0;
    end endtask
    initial begin
        repeat(5)@(negedge clk);rst_n=1;
        frame(1);if(committed!=4 || frame_available)$fatal(1,"Frame published before blank or before write completion");
        blank;wait(returned==4);repeat(3)@(negedge clk);
        if(!frame_available || error || !read_bank || write_bank)$fatal(1,"Bank initialization incorrect");
        // A real FWFT FIFO may already contain a complete frame. Its next
        // token follows immediately, including END behind the final pixel.
        // Keep command/data stalls independent while exercising that case.
        contiguous=1;
        frame(0);if(dut.pending_frame)$fatal(1,"Bad frame published");
        frame(1);if(!dut.pending_frame)$fatal(1,"Good next frame not published");
        display_full=1;frame(1);if(dropped_frames==0)$fatal(1,"Pending bank wasn't protected");
        returned=0;display_full=0;blank;wait(returned==4);
        if(read_bank || !write_bank || error)$fatal(1,"Second swap failed");
        $display("PASS: independent DDR command/data stalls, sparse/continuous tokens, complete writes before END, ordered pixels, bad-frame drop and bank protection");$finish;
    end
    initial begin #2000000;$fatal(1,"Watchdog");end
endmodule
