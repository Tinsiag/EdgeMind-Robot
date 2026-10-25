`timescale 1ns/1ps
module speed_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,tick=0;reg signed [31:0] delta=0;reg [31:0] cpr=1469,diameter=66300;
    wire signed [31:0] speed;
    a741_speed dut(.clk(clk),.rst_n(rst),.tick(tick),.delta(delta),.cpr(cpr),.diameter_um(diameter),.speed(speed));
    task sample(input signed [31:0] d);
        begin @(negedge clk);delta=d;tick=1;@(negedge clk);tick=0;repeat(68) @(negedge clk);end
    endtask
    initial begin
        #50;rst=1;sample(10);if(speed!=141) $fatal(1,"positive speed %d",speed);
        sample(-10);if(speed!= -141) $fatal(1,"signed speed");
        cpr=20000;diameter=200000;sample(20000);if(speed!=62840) $fatal(1,"28 bit divider bound %d",speed);
        cpr=100;sample(32'sh7fffffff);if(speed!=32'sh7fffffff) $fatal(1,"positive saturation");
        sample(32'sh80000000);if(speed!=-32'sh7fffffff) $fatal(1,"negative extreme/saturation");
        // Configuration and encoder delta belong to the same sampling tick.
        cpr=1469;diameter=66300;@(negedge clk);delta=-10;tick=1;
        @(negedge clk);tick=0;cpr=20000;diameter=200000;delta=100000;
        repeat(68) @(negedge clk);if(speed!=-141) $fatal(1,"in-flight sample changed");
        cpr=0;sample(100);if(speed!=0) $fatal(1,"unconfigured");
        $display("PASS pipelined wheel speed, signed counts, divisor bound and invalid config");$finish;
    end
endmodule
