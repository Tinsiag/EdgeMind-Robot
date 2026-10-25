`timescale 1ns/1ps
module cdc_fifo_tb;
    reg wr_clk=0,rd_clk=0;always #5 wr_clk=~wr_clk;always #7 rd_clk=~rd_clk;
    reg rst_n=0,wr_en=0,rd_en=0;reg [15:0] wr_data=0;
    wire full,empty;wire [15:0] rd_data;
    async_fifo #(.WIDTH(16),.ADDR_BITS(3)) fifo(.wr_clk(wr_clk),.wr_rst_n(rst_n),.wr_en(wr_en),.wr_data(wr_data),.full(full),.rd_clk(rd_clk),.rd_rst_n(rst_n),.rd_en(rd_en),.rd_data(rd_data),.empty(empty));
    integer written=0,read_count=0,i;
    always @(posedge wr_clk)if(rst_n && wr_en && !full)written=written+1;
    always @(posedge rd_clk)if(rst_n && rd_en && !empty)begin
        if(rd_data!==read_count)$fatal(1,"FIFO FWFT mismatch at %d got %d",read_count,rd_data);
        read_count=read_count+1;
    end
    reg src_valid=0;reg [63:0] src_data=0;wire src_ready,dst_valid;wire [63:0] dst_data;
    cdc_mailbox #(.WIDTH(64)) mailbox(.src_clk(wr_clk),.src_rst_n(rst_n),.src_valid(src_valid),.src_data(src_data),.src_ready(src_ready),.dst_clk(rd_clk),.dst_rst_n(rst_n),.dst_valid(dst_valid),.dst_data(dst_data));
    initial begin
        #40;rst_n=1;
        fork
            begin
                for(i=0;i<100;i=i+1) begin
                    @(negedge wr_clk);wr_en=0;
                    while(full)@(negedge wr_clk);
                    wr_data=i;wr_en=1;
                end
                @(negedge wr_clk);wr_en=0;
            end
            begin repeat(20)@(negedge rd_clk);rd_en=1;end
        join
        wait(read_count==100);
        @(negedge wr_clk);src_data=64'h123456789abcdef0;src_valid=1;
        @(negedge wr_clk);src_valid=0;src_data=0;
        wait(dst_valid);@(negedge rd_clk);if(dst_data!==64'h123456789abcdef0)$fatal(1,"Mailbox data torn");
        wait(src_ready);
        $display("PASS: asynchronous FIFO wrap/full/FWFT and bundled-data mailbox");$finish;
    end
    initial begin #100000;$fatal(1,"Watchdog");end
endmodule
