`timescale 1ns/1ps
module fifo_exercise #(parameter BITS=3)(output reg done=0);
    localparam DEPTH=1<<BITS;
    reg wr_clk=0,rd_clk=0;
    always #5 wr_clk=~wr_clk;
    always #7 rd_clk=~rd_clk;
    reg rst_n=0,wr_en=0,rd_en=0;
    reg [31:0] wr_data=0;
    wire [31:0] rd_data;
    wire full,empty;
    integer written=0,received=0,wcycle=0,rcycle=0,mode=0;
    async_fifo #(.WIDTH(32),.ADDR_BITS(BITS)) dut(
        .wr_clk(wr_clk),.wr_rst_n(rst_n),.wr_en(wr_en),.wr_data(wr_data),.full(full),
        .rd_clk(rd_clk),.rd_rst_n(rst_n),.rd_en(rd_en),.rd_data(rd_data),.empty(empty));
    always @(negedge wr_clk) begin
        wcycle=wcycle+1;
        wr_en=rst_n && (mode==1 || (mode==3 && wcycle%7!=0));
        wr_data=32'hcd000000+written;
    end
    always @(negedge rd_clk) begin
        rcycle=rcycle+1;
        rd_en=rst_n && (mode==2 || (mode==3 && rcycle%5!=0));
    end
    always @(posedge wr_clk)
        if(rst_n && wr_en && !full) written=written+1;
    always @(posedge rd_clk)
        if(rst_n && rd_en && !empty) begin
            if(rd_data!==32'hcd000000+received)
                $fatal(1,"FIFO bits=%0d index=%0d data=%h",BITS,received,rd_data);
            received=received+1;
        end
    task fill_and_drain;
        begin
            mode=1;wait(full);repeat(8) @(negedge wr_clk);
            if(written-received!=DEPTH) $fatal(1,"full capacity/overflow bits=%0d",BITS);
            mode=2;wait(empty);repeat(8) @(negedge rd_clk);
            if(written!=received) $fatal(1,"empty/underflow bits=%0d",BITS);
        end
    endtask
    initial begin
        #42;rst_n=1;
        fill_and_drain();
        mode=3;wait(received>DEPTH*4);mode=2;
        wait(empty);repeat(8) @(negedge rd_clk);
        if(written!=received) $fatal(1,"concurrent drain bits=%0d",BITS);
        mode=1;wait(full);mode=0;
        // Both domains reset together with unread entries still buffered.
        #2;rst_n=0;wr_en=0;rd_en=0;
        repeat(8) @(negedge rd_clk);
        written=0;received=0;
        #2;rst_n=1;
        fill_and_drain();
        done=1;
    end
endmodule

module async_fifo_tb;
    wire small_done,camera_done;
    fifo_exercise #(.BITS(3)) small_fifo(small_done);
    fifo_exercise #(.BITS(12)) camera_fifo(camera_done);
    initial begin
        wait(small_done && camera_done);
        $display("PASS async FIFO capacity, overflow/underflow, FWFT ordering, wrap, concurrent stalls and queued reset at 8/4096 entries");
        $finish;
    end
    initial begin #2000000;$fatal(1,"FIFO watchdog");end
endmodule
