`timescale 1ns/1ps
module acg720_motor_diag_duration_tb;
    reg clk=0;always #50000 clk=~clk; // 10 kHz; 10 clocks / real 1 kHz PWM period.
    reg stop_n=1,left_key_n=1,right_key_n=1;
    reg left_enc_a=0,left_enc_b=0,right_enc_a=0,right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;wire [7:0] led;
    integer n=0,high_count=0,high_period=0,cycles_run=0;
    // Keep production RUN_MS=1000 and RAMP_MS=200; shorten startup/debounce only.
    acg720_motor_diag_1khz_50 #(.CLK_HZ(10000),.STARTUP_MS(3),.DEBOUNCE_MS(2)) dut(.*);
    task cycles;input integer count;integer i;
        begin for(i=0;i<count;i=i+1) begin @(posedge clk);#1;end end
    endtask
    initial begin
        cycles(100);@(negedge clk);left_key_n=0;
        while(!led[1] && n<100) begin cycles(1);n=n+1;end
        if(!led[1]) $fatal(1,"No start");
        while(led[1] && cycles_run<10010) begin
            cycles(1);cycles_run=cycles_run+1;
            if(left_in1) high_count=high_count+1;
            if(cycles_run>2500 && cycles_run<=2510 && left_in1) high_period=high_period+1;
            if(right_in1||left_in2||right_in2) $fatal(1,"Wrong channel/polarity");
        end
        if(cycles_run<9990||cycles_run>10001||!led[5]) $fatal(1,"1-second bound cycles=%0d",cycles_run);
        if(high_period!=5) $fatal(1,"50%% plateau mismatch %0d/10",high_period);
        // At this reduced clock, 25% rounds to 2/10 clocks; expected about4550 high clocks.
        // Production 50MHz has no such 25% quantization.
        if(high_count<4540||high_count>4560) $fatal(1,"Ramp exposure mismatch %0d",high_count);
        cycles(11000);if(led[1]||left_in1) $fatal(1,"Held key repeated");
        $display("PASS diagnostic production 1000ms bound, 200ms ramp, 1kHz/50%% plateau, no repeat; cycles=%0d high=%0d",cycles_run,high_count);$finish;
    end
    initial begin #3000000000;$fatal(1,"Watchdog");end
endmodule
