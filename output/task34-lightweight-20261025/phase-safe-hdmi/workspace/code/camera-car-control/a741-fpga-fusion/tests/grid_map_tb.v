`timescale 1ns/1ps
module grid_map_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,clear=0,write_valid=0,read_valid=0;
    reg [6:0] write_x=0,write_y=0;reg [1:0] write_value=0;
    reg [13:0] read_address=0;
    wire [1:0] read_value;wire read_done,clear_busy,map_valid;wire [13:0] write_count;
    a741_grid_map dut(.clk(clk),.rst_n(rst_n),.clear(clear),.write_valid(write_valid),
        .write_x(write_x),.write_y(write_y),.write_value(write_value),.read_valid(read_valid),
        .read_address(read_address),.read_value(read_value),.read_done(read_done),
        .clear_busy(clear_busy),.map_valid(map_valid),.write_count(write_count));
    task read_cell(input [13:0] address,input [1:0] expected);
        begin @(negedge clk);read_address=address;read_valid=1;@(negedge clk);read_valid=0;
            if(!read_done || read_value!==expected) $fatal(1,"map read %0d got %0d expected %0d",address,read_value,expected);end
    endtask
    integer i;
    initial begin
        #30;rst_n=1;@(negedge clk);clear=1;@(negedge clk);clear=0;
        for(i=0;i<16384;i=i+1) @(negedge clk);
        if(!map_valid || clear_busy) $fatal(1,"map clear did not commit");
        read_cell(14'd0,2'b00);read_cell(14'd16383,2'b00);
        @(negedge clk);write_x=7'd3;write_y=7'd2;write_value=2'b01;write_valid=1;
        @(negedge clk);write_x=7'd4;write_value=2'b10;@(negedge clk);write_valid=0;
        read_cell(14'd259,2'b01);read_cell(14'd260,2'b10);
        if(write_count!=2) $fatal(1,"map update count");
        $display("PASS 128x128 map clear, occupancy writes and addressed reads");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
