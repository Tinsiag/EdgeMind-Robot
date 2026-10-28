`timescale 1ns/1ps
// Device-level check for the reset primitive used by a741_top.  A live FPGA
// reconfiguration must leave the powered TFT clock low until the display
// reset synchronizer releases it; this is the property the old plain ODDR
// could not provide.
module tft_clock_reset_tb;
    reg clk=0;
    reg clear=1;
    wire q0,q1;
    GSR GSR(.GSRI(1'b1));
    always #5 clk=~clk;

    ODDRC clock_out(.CLK(clk),.D0(1'b0),.D1(1'b1),.TX(1'b1),
        .CLEAR(clear),.Q0(q0),.Q1(q1));

    always @(q0 or q1) begin
        if(clear && (q0!==1'b0 || q1!==1'b0))
            $fatal(1,"TFT ODDRC was not held low during CLEAR");
    end

    initial begin
        #1;
        if({q1,q0}!==2'b00) $fatal(1,"TFT clock reset is not deterministic");
        #24;
        clear=0;
        // Allow both ODDRC halves to load after reset release.
        repeat(3) @(posedge clk);
        #1;
        if(q0!==1'b0) $fatal(1,"ODDRC high phase is wrong after release");
        @(negedge clk); #1;
        if(q0!==1'b1) $fatal(1,"ODDRC low phase is wrong after release");
        clear=1;
        #1;
        if({q1,q0}!==2'b00) $fatal(1,"TFT clock did not clear asynchronously");
        $display("PASS TFT ODDRC asynchronous clear and deterministic release");
        $finish;
    end
endmodule
