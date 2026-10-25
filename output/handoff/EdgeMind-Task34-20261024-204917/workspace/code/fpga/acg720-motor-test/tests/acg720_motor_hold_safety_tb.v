`timescale 1ns/1ps
module acg720_motor_hold_safety_tb;
    reg clk=0; always #5 clk=~clk;
    reg stop_n=1, left_key_n=0, right_key_n=1;
    reg left_enc_a=0, left_enc_b=0, right_enc_a=1, right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;
    wire [7:0] led;
    acg720_motor_hold_1khz_50 #(.CLK_HZ(100000),.STARTUP_MS(3),
        .DEBOUNCE_MS(2),.RUN_MS(300)) dut(.*);
    task cycles(input integer n);
        integer i; begin for(i=0;i<n;i=i+1) begin @(posedge clk);#1;end end
    endtask
    task idle;
        begin if(left_in1!==0 || right_in1!==0 || led[2:1]!==0)
            $fatal(1,"Unexpected drive");end
    endtask
    task release_keys;
        begin @(negedge clk);left_key_n=1;right_key_n=1;cycles(1000);idle;end
    endtask
    task await_run(input integer side);
        integer n; begin n=0;
            while(!led[side] && n<1000) begin cycles(1);n=n+1;end
            if(!led[side] || led[3-side]) $fatal(1,"Wrong selected channel");
        end
    endtask
    task left_ab(input [1:0] ab);
        begin @(negedge clk);{left_enc_b,left_enc_a}=ab;cycles(6);end
    endtask
    task right_ab(input [1:0] ab);
        begin @(negedge clk);{right_enc_b,right_enc_a}=ab;cycles(6);end
    endtask
    always @(posedge clk) begin
        #2;
        if(left_in2!==0 || right_in2!==0 || camera_reset_n!==0)
            $fatal(1,"Unexpected reverse input/camera release");
        if((left_in1 && right_in1) || led[2:1]==2'b11)
            $fatal(1,"Two wheels enabled");
        if((!stop_n || (!left_key_n && !right_key_n)) && (left_in1 || right_in1))
            $fatal(1,"Raw inhibit failed");
    end
    initial begin
        cycles(2000);idle;
        if(led[4:3]!==0) $fatal(1,"Static encoder level signalled activity");
        release_keys;
        @(negedge clk);left_key_n=0;cycles(50);idle;
        release_keys; // A sub-debounce pulse cannot start.
        @(negedge clk);left_key_n=0;await_run(1);
        cycles(10);
        left_ab(2'b11);left_ab(2'b00); // Illegal double-bit changes ignored.
        if(led[3]) $fatal(1,"Illegal AB jump signalled activity");
        left_ab(2'b01);left_ab(2'b11);left_ab(2'b10);
        if(led[3]) $fatal(1,"Activity latched before four legal edges");
        left_ab(2'b00);
        if(!led[3] || led[4]) $fatal(1,"Left encoder activity/mapping missing");
        // Release between clock edges, during a high PWM pulse.
        while(!left_in1) cycles(1);
        @(negedge clk);#1;left_key_n=1;#1;idle;
        cycles(2);@(negedge clk);left_key_n=0;cycles(1500);idle;
        release_keys;
        @(negedge clk);right_key_n=0;await_run(2);cycles(10);
        if(led[4:3]!==0) $fatal(1,"Activity not cleared on new attempt");
        right_ab(2'b11);right_ab(2'b10);right_ab(2'b00);right_ab(2'b01);
        if(!led[4] || led[3]) $fatal(1,"Right encoder activity/mapping missing");
        while(!right_in1) cycles(1);
        @(negedge clk);#1;stop_n=0;#1;idle;
        cycles(5);@(negedge clk);stop_n=1;cycles(2000);idle;
        release_keys;
        @(negedge clk);left_key_n=0;right_key_n=0;cycles(1500);idle;
        if(!led[6]) $fatal(1,"Chord not indicated");
        @(negedge clk);right_key_n=1;cycles(1500);idle;
        release_keys;
        @(negedge clk);left_key_n=0;await_run(1);
        while(!left_in1) cycles(1);
        @(negedge clk);#1;right_key_n=0;#1;idle;
        cycles(5);@(negedge clk);right_key_n=1;cycles(1500);idle;
        $display("PASS A71B: held-boot/bounce lockout, single-wheel routing, immediate release/S0/chord stop, no bounce restart, four legal encoder edges only");
        $finish;
    end
    initial begin #2000000;$fatal(1,"Watchdog");end
endmodule
