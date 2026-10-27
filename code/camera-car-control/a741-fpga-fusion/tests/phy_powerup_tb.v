`timescale 1ns/1ps
// Test production defaults in real nanoseconds, not an accelerated responder.
// A disconnected PHY must fail closed after a correctly delayed first read.
module phy_powerup_tb;
    reg clk=0,rst_n=0;always #10 clk=~clk;
    wire phy_rst_n,ready,error,mdc;tri1 mdio;
    a741_phy_config dut(.*);
    time reset_release,phy_release,first_mdc;
    integer edges=0,stopped;
    always @(posedge mdc) begin
        if(edges==0) begin
            first_mdc=$time;
            if(first_mdc-phy_release<50000000)
                $fatal(1,"PHY accessed before 50 ms settling: %0t",first_mdc-phy_release);
        end
        edges=edges+1;
    end
    initial begin
        #1;rst_n=1;#4;rst_n=0;#100;rst_n=1;reset_release=$time;
        @(posedge phy_rst_n);phy_release=$time;
        if(phy_release-reset_release<10000000) $fatal(1,"PHY reset shorter than 10 ms");
        wait(error);#1;
        if(ready || edges!=64 || mdio!==1 || mdc!==0) $fatal(1,"Absent PHY did not fail closed");
        stopped=edges;#2000000;
        if(edges!=stopped || ready) $fatal(1,"Unexpected automatic retry");
        rst_n=0;#1;
        if(phy_rst_n || ready || error || mdc) $fatal(1,"Reset did not clear terminal error");
        $display("PASS PHY production startup: reset >=10 ms, settle >=50 ms, absent PHY fails closed without retry");$finish;
    end
    initial begin #110000000;$fatal(1,"PHY startup watchdog");end
endmodule
