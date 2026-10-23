`timescale 1ns/1ps
module net_health_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,rx_good_frame=0,rx_bad_fcs=0;
    wire [7:0] status;
    a741_net_health dut(.*);
    integer i;
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        for(i=0;i<19;i=i+1) begin
            rx_good_frame=1;rx_bad_fcs=1;@(negedge clk);
        end
        rx_good_frame=0;rx_bad_fcs=0;
        repeat(3) @(negedge clk);
        if(status!=8'hf3) $fatal(1,"MAC count wrap/saturation %h",status);
        rst_n=0;@(negedge clk);
        if(status!=0) $fatal(1,"diagnostic reset");
        $display("PASS MAC diagnostics good-frame modulo, bad-FCS saturation and reset");$finish;
    end
endmodule
