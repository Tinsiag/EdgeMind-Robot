`timescale 1ns/1ps
module pi_target_limit_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,tick=0,enable=1;
    reg signed [31:0] target=0,measured=0;
    reg [9:0] target_limit=40;
    reg [15:0] speed_step=1000,pwm_step=512,limit=512;
    wire signed [31:0] applied,command;
    a741_pi #(.TARGET_LIMIT_ENABLED(1)) dut(.*);
    task sample;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;end
    endtask
    initial begin
        #30;rst_n=1;target=1000;sample();
        // Inputs changing after the tick must not change its sampled target.
        target=-1000;target_limit=5;repeat(25) @(negedge clk);
        if(applied!=40) $fatal(1,"target/cap were not sampled together %0d",applied);
        target=0;sample();target=1000;repeat(25) @(negedge clk);
        if(applied!=0 || command!=0) $fatal(1,"zero planning target retained drive");
        target=-1000;target_limit=7;sample();repeat(25) @(negedge clk);
        if(applied!=-7) $fatal(1,"negative target clamp %0d",applied);
        target=1000;target_limit=0;sample();repeat(25) @(negedge clk);
        if(applied || command) $fatal(1,"zero cap retained drive");
        target=1000;target_limit=50;sample();enable=0;@(negedge clk);
        if(applied || command) $fatal(1,"in-flight disable delayed");
        $display("PASS PI tick-atomic target/cap, signed clamp, zero target/cap and immediate disable");$finish;
    end
    initial begin #10000;$fatal(1,"PI limit watchdog");end
endmodule
