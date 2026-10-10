`timescale 1ns/1ps
module acg720_motor_test_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg stop_n = 1, left_key_n = 0, right_key_n = 1;
    reg left_enc_a = 0, left_enc_b = 0, right_enc_a = 1, right_enc_b = 0;
    wire left_in1, left_in2, right_in1, right_in2, camera_reset_n;
    wire [7:0] led;
    integer n, high_count, run_cycles, starts = 0;
    reg was_running = 0;

    // Shorten human delays while retaining the real top-level/reset/key logic.
    acg720_motor_test #(
        .CLK_HZ(10000), .PWM_HZ(100), .STARTUP_MS(5),
        .DEBOUNCE_MS(3), .RUN_MS(120), .RAMP_MS(8)
    ) dut(.*);

    task cycles(input integer count);
        integer k;
        begin for (k=0; k<count; k=k+1) begin @(posedge clk); #1; end end
    endtask
    task assert_idle;
        begin
            if (left_in1 !== 0 || right_in1 !== 0 || led[2:1] !== 0)
                $fatal(1, "Unexpected motor drive / busy indication");
        end
    endtask
    task await_left;
        integer k;
        begin
            k=0;
            while (!led[1] && k<200) begin cycles(1); k=k+1; end
            if (!led[1] || led[2]) $fatal(1, "Left key did not select left only");
        end
    endtask
    task await_right;
        integer k;
        begin
            k=0;
            while (!led[2] && k<200) begin cycles(1); k=k+1; end
            if (!led[2] || led[1]) $fatal(1, "Right key did not select right only");
        end
    endtask

    // These invariants also run during bouncing, startup and stop transitions.
    always @(posedge clk) begin
        #2;
        if (left_in2 !== 0 || right_in2 !== 0 || camera_reset_n !== 0)
            $fatal(1, "Reverse inputs/camera reset not held low");
        if ((left_in1 && right_in1) || led[2:1] == 2'b11)
            $fatal(1, "Both motors enabled by a single-wheel test");
        if (!stop_n && (left_in1 || right_in1)) $fatal(1, "S0 failed to stop");
        if ((|led[2:1]) && !was_running) starts=starts+1;
        was_running=|led[2:1];
    end

    initial begin
        // A held start key at configuration must never start a motor.
        cycles(220);
        assert_idle;
        if (led[4:3] !== 0) $fatal(1, "Static high encoder input caused false activity");
        @(negedge clk); left_key_n=1;
        cycles(100);
        // Sub-debounce pulses must not start.
        @(negedge clk); left_key_n=0; cycles(8);
        @(negedge clk); left_key_n=1; cycles(8);
        @(negedge clk); left_key_n=0; cycles(8);
        @(negedge clk); left_key_n=1; cycles(50);
        assert_idle;
        if (starts != 0) $fatal(1, "Held/bouncing key produced a start");
        $display("PASS: configuration-held key and bounce rejected, encoder startup baseline clean");

        @(negedge clk); left_key_n=0;
        await_left;
        run_cycles=0;
        cycles(105); run_cycles=run_cycles+105;
        @(negedge clk); left_enc_a=1;
        cycles(5); run_cycles=run_cycles+5;
        if (!led[3] || led[4]) $fatal(1, "Encoder activity mapped to wrong wheel");
        // After ramp, each complete 100-cycle period must be exactly 25%.
        repeat(3) begin
            high_count=0;
            for (n=0; n<100; n=n+1) begin
                cycles(1); run_cycles=run_cycles+1;
                if (left_in1) high_count=high_count+1;
                if (right_in1) $fatal(1, "Right motor driven during left test");
            end
            if (high_count != 25) $fatal(1, "PWM duty expected 25%%, got %0d/100", high_count);
        end
        while (led[1] && run_cycles<1300) begin cycles(1); run_cycles=run_cycles+1; end
        if (run_cycles<1190 || run_cycles>1202 || !led[5])
            $fatal(1, "Run timeout wrong: %0d cycles / completion=%b", run_cycles, led[5]);
        cycles(300);
        assert_idle;
        if (starts != 1) $fatal(1, "Held left key retriggered after timeout");
        $display("PASS: left-only 25%% PWM, encoder activity, bounded timeout, no held-key repeat");

        @(negedge clk); left_key_n=1;
        cycles(100);
        @(negedge clk); right_key_n=0;
        await_right;
        while (!right_in1) cycles(1);
        // Assert S0 between clock edges while PWM is high.
        #1; stop_n=0; #1;
        if (left_in1 !== 0 || right_in1 !== 0) $fatal(1, "Stop waits for clock");
        cycles(10);
        @(negedge clk); stop_n=1;
        cycles(220);
        assert_idle;
        if (starts != 2) $fatal(1, "Held key started motor after S0 release");
        $display("PASS: right-only test and asynchronous S0 stop, no restart on reset release");

        @(negedge clk); right_key_n=1;
        cycles(100);
        @(negedge clk); left_key_n=0; right_key_n=0;
        cycles(100);
        assert_idle;
        if (!led[6]) $fatal(1, "Two-button rejection indicator missing");
        @(negedge clk); left_key_n=1;
        cycles(100);
        assert_idle;
        // Releasing only one of a chord must not start the remaining wheel.
        @(negedge clk); right_key_n=1;
        cycles(100);
        @(negedge clk); right_key_n=0;
        await_right;
        @(negedge clk); right_enc_b=1;
        cycles(10);
        if (!led[4] || led[3]) $fatal(1, "Right encoder mapping/reset wrong");
        run_cycles=0;
        while (led[2] && run_cycles<1300) begin cycles(1); run_cycles=run_cycles+1; end
        if (!led[5]) $fatal(1, "Right timeout missing");
        cycles(200);
        assert_idle;
        if (starts != 3) $fatal(1, "Unexpected starts: %0d", starts);
        $display("PASS: chord rejection/rearm and right encoder; all motor safety checks passed");
        $finish;
    end
    initial begin #200000; $fatal(1, "Watchdog"); end
endmodule
