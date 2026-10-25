`timescale 1ns/1ps
`default_nettype none
module acg720_motor_sweep_tb;
    // Keep the real 50 kHz output and accelerate only duty dwell/debounce.
    // 5 MHz / 50 kHz = 100 clocks, so every percent remains exact.
    localparam integer CLK_HZ = 5000000;
    localparam integer TICKS_MS = CLK_HZ / 1000;
    localparam integer STEP_MS = 4;
    localparam integer PWM_CYCLES = CLK_HZ / 50000;
    reg clk = 0;
    always #100 clk = ~clk;
    reg stop_n = 1, left_key_n = 0, right_key_n = 0;
    reg left_enc_a = 1, left_enc_b = 0, right_enc_a = 0, right_enc_b = 1;
    wire left_in1, left_in2, right_in1, right_in2, camera_reset_n;
    wire [7:0] led;
    integer clock_count = 0;
    always @(posedge clk) clock_count = clock_count + 1;

    acg720_motor_sweep #(.CLK_HZ(CLK_HZ), .PWM_HZ(50000),
        .STARTUP_MS(3), .DEBOUNCE_MS(2), .STEP_MS(STEP_MS), .STEP_PERCENT(5)) dut (
        .clk(clk), .stop_n(stop_n), .left_key_n(left_key_n), .right_key_n(right_key_n),
        .left_enc_a(left_enc_a), .left_enc_b(left_enc_b),
        .right_enc_a(right_enc_a), .right_enc_b(right_enc_b),
        .left_in1(left_in1), .left_in2(left_in2), .right_in1(right_in1), .right_in2(right_in2),
        .camera_reset_n(camera_reset_n), .led(led));

    task cycles;
        input integer count;
        integer n;
        begin
            if (count < 0) $fatal(1, "Missed scheduled waveform sample");
            for (n = 0; n < count; n = n + 1) begin @(posedge clk); #1; end
        end
    endtask
    task mask;
        input [1:0] expected;
        integer n;
        begin
            n = 0;
            while (led[2:1] !== expected && n < 10 * TICKS_MS) begin
                cycles(1); n = n + 1;
            end
            if (led[2:1] !== expected) $fatal(1, "Toggle mask mismatch: %b", led[2:1]);
            if (!expected[0] && left_in1 !== 0) $fatal(1, "Stopped left output high");
            if (!expected[1] && right_in1 !== 0) $fatal(1, "Stopped right output high");
        end
    endtask
    task release_key;
        input integer side;
        begin
            @(negedge clk);
            if (side == 0) left_key_n = 1; else right_key_n = 1;
            cycles(6 * TICKS_MS);
        end
    endtask
    task press_key;
        input integer side;
        begin
            @(negedge clk);
            if (side == 0) left_key_n = 0; else right_key_n = 0;
        end
    endtask
    task measure;
        input integer side;
        input integer duty_percent;
        integer n, high_count, rise_count;
        reg previous_value, current_value;
        begin
            high_count = 0; rise_count = 0;
            previous_value = side == 0 ? left_in1 : right_in1;
            // Three full periods: exact high count and 50 kHz edge count,
            // regardless of starting phase. Endpoints have no switching edges.
            for (n = 0; n < 3 * PWM_CYCLES; n = n + 1) begin
                cycles(1);
                current_value = side == 0 ? left_in1 : right_in1;
                if (current_value) high_count = high_count + 1;
                if (current_value && !previous_value) rise_count = rise_count + 1;
                previous_value = current_value;
            end
            if (high_count != 3 * duty_percent)
                $fatal(1, "Side %0d: duty %0d%% high=%0d expected=%0d",
                    side, duty_percent, high_count, 3 * duty_percent);
            if (rise_count != ((duty_percent == 0 || duty_percent == 100) ? 0 : 3))
                $fatal(1, "Side %0d: incorrect PWM frequency at %0d%%", side, duty_percent);
        end
    endtask
    always @(negedge clk) begin
        if (left_in2 !== 0 || right_in2 !== 0 || camera_reset_n !== 0)
            $fatal(1, "Unexpected direction/camera output");
        if (!led[1] && left_in1 !== 0) $fatal(1, "Idle left output high");
        if (!led[2] && right_in1 !== 0) $fatal(1, "Idle right output high");
    end

    integer start_cycle, stage, duty_percent;
    initial begin
        cycles(12 * TICKS_MS); mask(0);
        if (led[4:3] !== 0) $fatal(1, "Static encoder input produced false activity");
        release_key(0); release_key(1);
        press_key(0); cycles(TICKS_MS / 5); release_key(0); mask(0);
        press_key(0); mask(1); start_cycle = clock_count;
        // All 21 levels, wrap, then a second complete sweep. A held key must
        // survive the first full cycle; release during the second cycle.
        for (stage = 0; stage < 42; stage = stage + 1) begin
            cycles(start_cycle + (stage * STEP_MS + 1) * TICKS_MS - clock_count);
            duty_percent = (stage % 21) * 5;
            measure(0, duty_percent); mask(1);
            if (led[6] !== (duty_percent == 100)) $fatal(1, "Maximum-duty indicator mismatch");
            if (stage == 35) begin @(negedge clk); left_key_n = 1; end
        end
        if (!left_in1 || !led[6]) $fatal(1, "Expected continuous high at 100%%");
        press_key(0); mask(0);
        cycles(6 * TICKS_MS); mask(0); // Holding after stop must not restart.
        release_key(0); press_key(0); mask(1);
        cycles(TICKS_MS); measure(0, 0); // Every manual restart begins at zero.
        cycles(4 * TICKS_MS); measure(0, 5);

        press_key(1); mask(3); start_cycle = clock_count;
        for (stage = 0; stage < 22; stage = stage + 1) begin
            cycles(start_cycle + (stage * STEP_MS + 1) * TICKS_MS - clock_count);
            measure(1, (stage % 21) * 5); mask(3);
        end
        left_enc_a = 0; right_enc_b = 0; cycles(10);
        if (led[4:3] !== 2'b11) $fatal(1, "Encoder activity was not recorded");
        release_key(1); press_key(1); mask(1);
        cycles(6 * TICKS_MS); mask(1);
        // Stopping/restarting left must preserve right's encoder history.
        release_key(0); press_key(0); mask(0);
        release_key(0); press_key(0); mask(1);
        if (led[3] || !led[4]) $fatal(1, "Restart cleared wrong encoder record");
        cycles(TICKS_MS); measure(0, 0);
        release_key(1); press_key(1); mask(3);
        wait(left_in1 && right_in1); #27; stop_n = 0; #1;
        if (left_in1 !== 0 || right_in1 !== 0) $fatal(1, "S0 did not stop asynchronously");
        left_key_n = 0; right_key_n = 0;
        #400; stop_n = 1; cycles(12 * TICKS_MS); mask(0);
        release_key(0); press_key(0); mask(1);
        cycles(TICKS_MS); measure(0, 0); // Other held key remains locked out.
        stop_n = 0; #1;
        if (left_in1 || right_in1) $fatal(1, "Final stop failed");
        $display("PASS: 50 kHz; all 0..100%% levels; two left sweeps; right sweep/wrap; independent toggle/restart; held/bounced keys; encoder history; asynchronous S0");
        $finish;
    end
    initial begin #1000000000; $fatal(1, "Watchdog expired"); end
endmodule
`default_nettype wire
