`timescale 1us/1ns
module button_debounce_tb;
    reg clk=0; always #0.5 clk=~clk; // 1 MHz
    reg rst_n=0, button_n=0;
    wire press;
    a741_button_debounce #(.CLK_HZ(1000000),.DEBOUNCE_MS(2)) dut(
        .clk(clk),.rst_n(rst_n),.button_n(button_n),.press(press));
    integer presses;
    always @(posedge clk) if(press) presses=presses+1;
    initial begin
        presses=0;
        // Power-on held S1 is ignored.
        #3; rst_n=1; #4000;
        if(presses!=0) $fatal(1,"held S1 generated a press");
        // Release, then press once with contact bounce.
        button_n=1; #3000; button_n=0; #300; button_n=1; #200; button_n=0; #3000;
        if(presses!=1) $fatal(1,"debounced press count=%0d",presses);
        // Long hold produces one event only.
        #10000;
        if(presses!=1) $fatal(1,"long hold retriggered");
        button_n=1; #3000;
        button_n=0; #3000;
        if(presses!=2) $fatal(1,"second press count=%0d",presses);
        $display("PASS S1 release qualification, debounce, long-hold and one-shot");
        $finish;
    end
    initial begin #40000; $fatal(1,"button debounce watchdog"); end
endmodule
