`timescale 1ns/1ps
module acg720_gpio_static_tb;
    reg clk=0;always #5 clk=~clk;
    reg stop_n=1,left_key_n=0,right_key_n=1;
    reg left_enc_a=0,left_enc_b=0,right_enc_a=0,right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;
    wire [7:0] led;
    acg720_gpio_static #(.CLK_HZ(10000),.STARTUP_MS(3),.DEBOUNCE_MS(3)) dut(.*);
    task cycles;input integer n;integer i;begin for(i=0;i<n;i=i+1) begin @(posedge clk);#1;end end endtask
    task low;begin if(left_in1!==0||left_in2!==0) $fatal(1,"Expected left low");end endtask
    always @(posedge clk) begin
        #2;
        if(right_in1!==0||right_in2!==0||camera_reset_n!==0) $fatal(1,"Unexpected right/camera output");
        if(left_in1&&left_in2) $fatal(1,"Both left outputs high");
        if((!stop_n||(!left_key_n&&!right_key_n))&&(left_in1||left_in2)) $fatal(1,"Inhibit failed");
    end
    initial begin
        cycles(200);low; // held at configuration cannot activate
        @(negedge clk);left_key_n=1;cycles(100);low;
        @(negedge clk);left_key_n=0;cycles(7);low;
        @(negedge clk);left_key_n=1;cycles(50);low;
        @(negedge clk);left_key_n=0;cycles(80);
        if(!left_in1||left_in2||!led[1]) $fatal(1,"S1 IN1 high missing");
        cycles(5000);if(!left_in1) $fatal(1,"Not static while held");
        #1;left_key_n=1;#1;low;cycles(100);
        @(negedge clk);right_key_n=0;cycles(80);
        if(left_in1||!left_in2||!led[2]) $fatal(1,"S2 IN2 high missing");
        #1;stop_n=0;#1;low;cycles(5);
        @(negedge clk);stop_n=1;cycles(200);low;
        @(negedge clk);right_key_n=1;cycles(100);
        @(negedge clk);left_key_n=0;right_key_n=0;cycles(100);low;
        @(negedge clk);right_key_n=1;cycles(100);low; // chord does not select leftover key
        @(negedge clk);left_key_n=1;cycles(100);
        @(negedge clk);left_key_n=0;cycles(80);
        if(!left_in1) $fatal(1,"Did not rearm after both released");
        #1;right_key_n=0;#1;low;cycles(10);
        @(negedge clk);left_key_n=1;right_key_n=1;cycles(100);
        @(negedge clk);left_enc_a=1;left_enc_b=1;right_enc_a=1;right_enc_b=1;
        cycles(5);if(led[6:3]!=4'b1111) $fatal(1,"Live AB indicators incorrect");
        low;
        $display("PASS A719 static S1/S2, release/S0 immediate low, debounce, held-start lockout, chord rejection, right-low, live AB");$finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
