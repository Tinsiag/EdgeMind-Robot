`timescale 1ns/1ps
module clkdiv_phase_tb;
    reg serial_clk=0, reset_n=0;
    wire pixel_clk;
    GSR GSR(.GSRI(1'b1));
    always #3 serial_clk=~serial_clk;
    CLKDIV #(.DIV_MODE("5")) divider(.CLKOUT(pixel_clk),.CALIB(1'b1),
        .HCLKIN(serial_clk),.RESETN(reset_n));
    integer trial, phase, mask=0;
    // Six-ns fast clock and 30-ns pixel clock keep phase calculations exact.
    // Sweep the release of the real vendor CLKDIV, without assuming its
    // initial phase equals that of another PLL output divided by five.
    initial begin
        for(trial=0;trial<5;trial=trial+1) begin
            reset_n=0;
            #(300-($time%300));
            #60;
            #(trial*6+1);
            reset_n=1;
            repeat(5) @(posedge pixel_clk);
            phase=($time-3)%30;
            mask=mask | (1 << (phase/6));
            $display("trial=%0d time=%0t relative_phase_ns=%0d",trial,$time,phase);
            #1;
        end
        if(mask!=31) $fatal(1,"expected all five integer-cycle phases, mask=%0d",mask);
        $display("PASS: asynchronous CLKDIV release permits all five pixel-clock phases");
        $finish;
    end
    initial begin #10000; $fatal(1,"phase experiment timeout"); end
endmodule
