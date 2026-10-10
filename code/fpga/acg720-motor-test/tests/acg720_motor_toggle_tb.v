`timescale 1ns/1ps
module acg720_motor_toggle_tb;
    reg clk = 0;
`ifdef TOGGLE50K80_TEST
    localparam TEST_CLK_HZ = 500000;
    always #1000 clk = ~clk;
`else
    localparam TEST_CLK_HZ = 100000;
    always #5000 clk = ~clk;
`endif
    localparam TICKS_MS = TEST_CLK_HZ / 1000;
    reg stop_n = 1, left_key_n = 0, right_key_n = 0;
    reg left_enc_a = 1, left_enc_b = 0, right_enc_a = 0, right_enc_b = 1;
    wire left_in1, left_in2, right_in1, right_in2, camera_reset_n;
    wire [7:0] led;
    integer high_count, rise_count, k;
    reg previous_pwm, observed_pwm;
`ifdef TOGGLE50K80_TEST
    localparam EXPECT_HIGH = 80;
    localparam EXPECT_RISES = 50;
    localparam PWM_TEST_HZ = 50000;
    acg720_motor_toggle_50khz_80 #(
`elsif TOGGLE20K80_TEST
    localparam EXPECT_HIGH = 80;
    localparam EXPECT_RISES = 20;
    localparam PWM_TEST_HZ = 20000;
    acg720_motor_toggle_20khz_80 #(
`elsif TOGGLE80_TEST
    localparam EXPECT_HIGH = 80;
    localparam EXPECT_RISES = 1;
    localparam PWM_TEST_HZ = 1000;
    acg720_motor_toggle_80 #(
`else
    localparam EXPECT_HIGH = 65;
    localparam EXPECT_RISES = 1;
    localparam PWM_TEST_HZ = 1000;
    acg720_motor_toggle #(
`endif
        .CLK_HZ(TEST_CLK_HZ), .STARTUP_MS(3), .DEBOUNCE_MS(2), .RAMP_MS(40)
    ) dut(.*);

    task cycles(input integer count);
        integer i;
        begin for (i=0; i<count; i=i+1) begin @(posedge clk); #1; end end
    endtask
    task mask(input [1:0] expected);
        integer n;
        begin
            n=0;
            while (led[2:1] !== expected && n<TICKS_MS*10) begin cycles(1); n=n+1; end
            if (led[2:1] !== expected) $fatal(1, "Expected run mask %b, got %b", expected, led[2:1]);
            if (!expected[0] && left_in1 !== 0) $fatal(1, "Stopped left still driven");
            if (!expected[1] && right_in1 !== 0) $fatal(1, "Stopped right still driven");
        end
    endtask
    task release_left;
        begin @(negedge clk); left_key_n=1; cycles(TICKS_MS*10); end
    endtask
    task release_right;
        begin @(negedge clk); right_key_n=1; cycles(TICKS_MS*10); end
    endtask
    task pwm_platform(input integer side);
        begin
            repeat (3) begin
                high_count=0;
                rise_count=0;
                previous_pwm = side == 0 ? left_in1 : right_in1;
                for (k=0; k<TICKS_MS; k=k+1) begin
                    cycles(1);
                    observed_pwm = side == 0 ? left_in1 : right_in1;
                    if (observed_pwm) high_count=high_count+1;
                    if (observed_pwm && !previous_pwm) rise_count=rise_count+1;
                    previous_pwm = observed_pwm;
                end
                if (high_count != TICKS_MS*EXPECT_HIGH/100) $fatal(1, "Wrong %0d%% PWM for side %0d, high_count=%0d/%0d", EXPECT_HIGH, side, high_count, TICKS_MS);
                if (rise_count != EXPECT_RISES) $fatal(1, "Wrong PWM frequency: expected %0d rises per ms, got %0d", EXPECT_RISES, rise_count);
            end
        end
    endtask
    always @(posedge clk) begin
        #2;
        if (left_in2 !== 0 || right_in2 !== 0 || camera_reset_n !== 0)
            $fatal(1, "Unexpected reverse input or camera release");
    end
    initial begin
        cycles(TICKS_MS*20); mask(0);
        if (led[4:3] !== 0) $fatal(1, "Static encoder high falsely reported activity");
        release_left; release_right;
        // Short contact bounce must not start either motor.
        @(negedge clk); left_key_n=0; cycles(TICKS_MS/5);
        @(negedge clk); left_key_n=1; cycles(TICKS_MS*10); mask(0);
        @(negedge clk); left_key_n=0; mask(1);
        cycles(TICKS_MS*41); pwm_platform(0);
        cycles(TICKS_MS*2500); mask(1); // > 2 seconds, held key cannot repeat or time out.
        $display("PASS: no held-key/bounce start, %0d Hz %0d%% PWM persists beyond old timeout", PWM_TEST_HZ, EXPECT_HIGH);
        release_left;
        @(negedge clk); left_key_n=0; mask(0);
        cycles(TICKS_MS*20); mask(0); // Stop press held cannot restart.
        release_left;
        @(negedge clk); left_key_n=0; mask(1);
        @(negedge clk); right_key_n=0; mask(3);
        cycles(TICKS_MS*41); pwm_platform(0); pwm_platform(1);
        @(negedge clk); left_enc_a=0; right_enc_b=0;
        cycles(10);
        if (led[4:3] !== 2'b11) $fatal(1, "Both encoder events missing");
        release_left;
        @(negedge clk); left_key_n=0; mask(2); pwm_platform(1);
        release_left;
        @(negedge clk); left_key_n=0; mask(3);
        if (led[3] !== 0 || led[4] !== 1) $fatal(1, "Starting left must clear only left encoder history");
        release_left; release_right;
        @(negedge clk); left_key_n=0; right_key_n=0; mask(0);
        cycles(TICKS_MS*10); mask(0);
        release_left; release_right;
        @(negedge clk); left_key_n=0; right_key_n=0; mask(3);
        $display("PASS: second press stops, independent toggles and simultaneous two-wheel operation");
        while (!left_in1 || !right_in1) cycles(1);
        #10; stop_n=0; #1;
        if (left_in1 !== 0 || right_in1 !== 0) $fatal(1, "S0 must stop both between clock edges");
        cycles(5);
        @(negedge clk); stop_n=1;
        cycles(TICKS_MS*20); mask(0); // Both keys held through reset cannot start.
        release_left;
        @(negedge clk); left_key_n=0; mask(1); // Other key is still held, stays stopped.
        $display("PASS: asynchronous all-stop, reset-held lockout, each key rearms independently");
        $finish;
    end
    initial begin #4000000000; $fatal(1, "Watchdog"); end
endmodule
