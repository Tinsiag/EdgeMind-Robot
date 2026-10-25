`timescale 1ns/1ps
module motor_pwm_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,enable=0;reg signed [31:0] command=0;
    wire in1,in2;wire [15:0] pwm_abs;
    motor_pwm_safe #(.CLK_HZ(100000),.PWM_HZ(1000),.INVERT(1)) dut(.*);
    integer i,ones,blank;
    initial begin
        repeat(3)@(negedge clk);rst_n=1;enable=1;command=512;
        repeat(205)@(negedge clk);
        ones=0;for(i=0;i<100;i=i+1)begin @(negedge clk);if(in1)$fatal(1,"Positive right command wrong bridge polarity");if(in2)ones=ones+1;end
        if(ones!=50)$fatal(1,"PWM not 50 percent: %d",ones);
        command=128;@(negedge clk);
        if(dut.magnitude_q!=512)$fatal(1,"Duty changed mid-period");
        repeat(100)@(negedge clk);
        command=-512;blank=0;
        repeat(300)begin @(negedge clk);if(dut.dead)blank=blank+1;if(in1 && in2)$fatal(1,"Both bridge inputs high");end
        if(blank<100)$fatal(1,"No full reversal blank period");
        if(pwm_abs!=512)$fatal(1,"Reverse command not applied");
        enable=0;#1;if(in1 || in2 || pwm_abs!=0)$fatal(1,"STOP waited for PWM boundary");
        $display("PASS: bridge sign after PI, period duty latch, reversal dead period, immediate disable");$finish;
    end
endmodule
