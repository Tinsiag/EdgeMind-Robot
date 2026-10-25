`timescale 1ns/1ps
module lidar_control_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,ms_tick=0,enabled=1,update=0,renew=0,stop=0;
    reg [9:0] duty_request=400;
    wire pwm;wire [31:0] status;
    ld06_control #(.CLK_HZ(3000000),.ACQUIRE_MS(3),.LEASE_MS(8)) dut(.*);
    task ms;begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end endtask
    task command(input [9:0] d);begin @(negedge clk);duty_request=d;update=1;@(negedge clk);update=0;repeat(80) @(negedge clk);end endtask
    integer n,highs;
    task duty(input integer expected);begin
        highs=0;repeat(100) begin @(negedge clk);if(pwm) highs=highs+1;end
        if(highs!=expected) $fatal(1,"PWM high clocks %0d expected %0d",highs,expected);
    end endtask
    initial begin
        #50;rst_n=1;repeat(20) @(negedge clk);if(pwm || status[23]) $fatal(1,"radar started without command");
        command(400);duty(50);repeat(3) ms();repeat(2) @(negedge clk);duty(40);
        repeat(4) begin ms();@(negedge clk);renew=1;@(negedge clk);renew=0;end
        duty(40);stop=1;#1;if(pwm) $fatal(1,"stop not immediate");@(negedge clk);stop=0;duty(0);
        command(600);repeat(3) ms();repeat(3) @(negedge clk);duty(60);
        repeat(9) ms();if(pwm || !status[21]) $fatal(1,"lease expiry");
        renew=1;@(negedge clk);renew=0;repeat(3) @(negedge clk);duty(0);
        command(400);duty(50);stop=1;@(negedge clk);stop=0;duty(0);
        command(400);enabled=0;@(negedge clk);enabled=1;duty(0);
        $display("PASS LD06 startup acquisition, bounded PWM, STOP, expiry and explicit restart");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
