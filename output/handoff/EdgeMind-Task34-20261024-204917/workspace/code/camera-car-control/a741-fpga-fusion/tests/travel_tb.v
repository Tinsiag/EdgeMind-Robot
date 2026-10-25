`timescale 1ns/1ps
module travel_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0;reg signed [31:0] delta=1;reg [31:0] cpr=1469,diameter_um=66300;
    wire done,valid;wire signed [31:0] distance_q16;
    a741_travel dut(.*);
    task sample(input integer d);
        begin @(negedge clk);delta=d;start=1;@(negedge clk);start=0;wait(done);@(negedge clk);end
    endtask
    reg signed [63:0] expected;integer n;
    initial begin
        #30;rst_n=1;
        for(n=-100;n<=100;n=n+1) begin
            sample(n);expected=$signed(n)*64'sd66300*64'sd3142*64'sd65536/(64'sd1469*64'sd1000000);
            if(!valid || distance_q16!=expected) $fatal(1,"Q16 travel mismatch n=%0d got=%0d expected=%0d",n,distance_q16,expected);
        end
        cpr=0;sample(1);if(valid || distance_q16) $fatal(1,"invalid CPR allowed integration");
        cpr=1469;sample(2147483647);if(valid || distance_q16) $fatal(1,"overflow allowed integration");
        $display("PASS signed Q16 encoder travel, sub-mm counts, config and overflow rejection");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
