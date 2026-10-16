`timescale 1ns/1ps
module wheel_speed_estimator_tb;
    reg clk=0,rstn=0,tick=0; reg signed [31:0] delta=0; reg [31:0] cpr=1456,diam=80;
    wire signed [31:0] speed; wire valid;
    always #5 clk=~clk;
    wheel_speed_estimator dut(.clk(clk),.rstn(rstn),.sample_tick(tick),.delta_count(delta),.cpr(cpr),.diameter_mm(diam),.speed_mm_s(speed),.valid(valid));
    initial begin
        #20; rstn=1; @(negedge clk); delta=10; tick=1; @(negedge clk); tick=0;
        wait(valid); if(speed<=0) $fatal(1,"speed conversion failed: %0d",speed);
        $display("PASS speed estimator speed=%0d",speed); $finish;
    end
    initial begin #10000 $fatal(1,"speed watchdog"); end
endmodule
