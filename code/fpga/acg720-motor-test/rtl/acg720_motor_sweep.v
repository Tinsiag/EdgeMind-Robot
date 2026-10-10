`timescale 1ns/1ps
`default_nettype none

// S1/S2 toggle independent 0..100% duty sweeps. Starts stopped; held keys never repeat.
// IN1=PWM, IN2=0; output polarity has not yet been mapped to vehicle forward.
module acg720_motor_sweep #(
    parameter integer CLK_HZ = 50000000,
    parameter integer PWM_HZ = 50000,
    parameter integer STARTUP_MS = 100,
    parameter integer DEBOUNCE_MS = 20,
    parameter integer STEP_MS = 500,
    parameter integer STEP_PERCENT = 5
)(
    input wire clk,
    input wire stop_n,
    input wire left_key_n,
    input wire right_key_n,
    input wire left_enc_a,
    input wire left_enc_b,
    input wire right_enc_a,
    input wire right_enc_b,
    output wire left_in1,
    output wire left_in2,
    output wire right_in1,
    output wire right_in2,
    output wire camera_reset_n,
    output wire [7:0] led
);
    localparam integer STARTUP_CYCLES = (CLK_HZ / 1000) * STARTUP_MS;
    localparam integer MS_CYCLES = CLK_HZ / 1000;
    localparam integer PWM_CYCLES = CLK_HZ / PWM_HZ;
    localparam integer MS_WIDTH = $clog2(MS_CYCLES + 1);
    localparam integer PWM_WIDTH = $clog2(PWM_CYCLES + 1);
    localparam integer DEBOUNCE_WIDTH = $clog2(DEBOUNCE_MS + 1);
    localparam integer STEP_WIDTH = $clog2(STEP_MS + 1);
    localparam integer DUTY_STEP_CYCLES = PWM_CYCLES * STEP_PERCENT / 100;

    // synthesis translate_off
    initial begin
        if (CLK_HZ % 1000 != 0 || CLK_HZ % PWM_HZ != 0 ||
            PWM_CYCLES % 100 != 0 || STEP_PERCENT < 1 || STEP_PERCENT > 100 ||
            100 % STEP_PERCENT != 0 || STEP_MS < 1 || DEBOUNCE_MS < 1 || STARTUP_MS < 1)
            $fatal(1, "Sweep requires whole milliseconds/PWM periods and exact duty steps");
    end
    // synthesis translate_on

    reg [31:0] startup_count = 0;
    reg startup_done = 0;
    reg [1:0] reset_release = 0;
    always @(posedge clk or negedge stop_n) begin
        if (!stop_n) begin
            startup_count <= 0;
            startup_done <= 0;
            reset_release <= 0;
        end else begin
            if (!startup_done) begin
                if (startup_count == STARTUP_CYCLES - 1)
                    startup_done <= 1;
                else
                    startup_count <= startup_count + 1'b1;
            end
            reset_release <= {reset_release[0], startup_done};
        end
    end
    wire reset_n = stop_n && reset_release[1];

    (* syn_preserve = 1 *) reg [1:0] key_meta = 0;
    (* syn_preserve = 1 *) reg [1:0] key_sync = 0;
    (* syn_preserve = 1 *) reg [3:0] enc_meta = 0;
    (* syn_preserve = 1 *) reg [3:0] enc_sync = 0;
    reg [3:0] enc_previous = 0;
    reg [2:0] encoder_valid = 0;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            key_meta <= 0;
            key_sync <= 0;
            enc_meta <= 0;
            enc_sync <= 0;
            enc_previous <= 0;
            encoder_valid <= 0;
        end else begin
            key_meta <= ~{right_key_n, left_key_n};
            key_sync <= key_meta;
            enc_meta <= {right_enc_b, right_enc_a, left_enc_b, left_enc_a};
            enc_sync <= enc_meta;
            enc_previous <= enc_sync;
            encoder_valid <= {encoder_valid[1:0], 1'b1};
        end
    end

    reg [MS_WIDTH-1:0] ms_counter = 0;
    wire ms_tick = ms_counter == MS_CYCLES - 1;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n)
            ms_counter <= 0;
        else if (ms_tick)
            ms_counter <= 0;
        else
            ms_counter <= ms_counter + 1'b1;
    end

    reg [1:0] key_pressed = 0;
    reg [DEBOUNCE_WIDTH-1:0] left_debounce = 0;
    reg [DEBOUNCE_WIDTH-1:0] right_debounce = 0;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            key_pressed <= 0;
            left_debounce <= 0;
            right_debounce <= 0;
        end else if (ms_tick) begin
            if (key_sync[0] == key_pressed[0])
                left_debounce <= 0;
            else if (left_debounce == DEBOUNCE_MS - 1) begin
                key_pressed[0] <= key_sync[0];
                left_debounce <= 0;
            end else
                left_debounce <= left_debounce + 1'b1;
            if (key_sync[1] == key_pressed[1])
                right_debounce <= 0;
            else if (right_debounce == DEBOUNCE_MS - 1) begin
                key_pressed[1] <= key_sync[1];
                right_debounce <= 0;
            end else
                right_debounce <= right_debounce + 1'b1;
        end
    end

    reg [1:0] key_previous = 0;
    reg [1:0] armed = 0;
    reg [DEBOUNCE_WIDTH-1:0] left_release = 0;
    reg [DEBOUNCE_WIDTH-1:0] right_release = 0;
    reg [1:0] run_mask = 0;
    reg [STEP_WIDTH-1:0] left_step_ms = 0;
    reg [STEP_WIDTH-1:0] right_step_ms = 0;
    // Width includes PWM_CYCLES itself: 100% must not overflow to zero.
    reg [PWM_WIDTH-1:0] left_duty = 0;
    reg [PWM_WIDTH-1:0] right_duty = 0;
    wire [PWM_WIDTH:0] left_duty_sum = {1'b0, left_duty} + DUTY_STEP_CYCLES;
    wire [PWM_WIDTH:0] right_duty_sum = {1'b0, right_duty} + DUTY_STEP_CYCLES;
    reg left_seen = 0;
    reg right_seen = 0;
    wire [1:0] toggle_event = key_pressed & ~key_previous & armed;

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            key_previous <= 0;
            armed <= 0;
            left_release <= 0;
            right_release <= 0;
            run_mask <= 0;
            left_step_ms <= 0;
            left_duty <= 0;
            right_step_ms <= 0;
            right_duty <= 0;
            left_seen <= 0;
            right_seen <= 0;
        end else begin
            key_previous <= key_pressed;
            if (encoder_valid[2] && |(enc_sync[1:0] ^ enc_previous[1:0])) left_seen <= 1;
            if (encoder_valid[2] && |(enc_sync[3:2] ^ enc_previous[3:2])) right_seen <= 1;

            // Each key must be released before its next press can toggle.
            if (!key_sync[0] && !key_pressed[0]) begin
                if (ms_tick && !armed[0]) begin
                    if (left_release == DEBOUNCE_MS - 1) begin
                        armed[0] <= 1;
                        left_release <= 0;
                    end else
                        left_release <= left_release + 1'b1;
                end
            end else
                left_release <= 0;
            if (!key_sync[1] && !key_pressed[1]) begin
                if (ms_tick && !armed[1]) begin
                    if (right_release == DEBOUNCE_MS - 1) begin
                        armed[1] <= 1;
                        right_release <= 0;
                    end else
                        right_release <= right_release + 1'b1;
                end
            end else
                right_release <= 0;

            if (ms_tick) begin
                if (run_mask[0]) begin
                    if (left_step_ms == STEP_MS - 1) begin
                        left_step_ms <= 0;
                        // Exact steps reach PWM_CYCLES; no valid sum exceeds it.
                        left_duty <= left_duty == PWM_CYCLES ? 0 : left_duty_sum[PWM_WIDTH-1:0];
                    end else
                        left_step_ms <= left_step_ms + 1'b1;
                end
                if (run_mask[1]) begin
                    if (right_step_ms == STEP_MS - 1) begin
                        right_step_ms <= 0;
                        right_duty <= right_duty == PWM_CYCLES ? 0 : right_duty_sum[PWM_WIDTH-1:0];
                    end else
                        right_step_ms <= right_step_ms + 1'b1;
                end
            end
            if (toggle_event[0]) begin
                run_mask[0] <= ~run_mask[0];
                armed[0] <= 0;
                left_release <= 0;
                left_step_ms <= 0;
                left_duty <= 0;
                if (!run_mask[0]) left_seen <= 0;
            end
            if (toggle_event[1]) begin
                run_mask[1] <= ~run_mask[1];
                armed[1] <= 0;
                right_release <= 0;
                right_step_ms <= 0;
                right_duty <= 0;
                if (!run_mask[1]) right_seen <= 0;
            end
        end
    end

    // Apply each new duty at a PWM boundary to avoid partial pulses.
    reg [PWM_WIDTH-1:0] left_active_duty = 0;
    reg [PWM_WIDTH-1:0] right_active_duty = 0;
    reg [PWM_WIDTH-1:0] pwm_counter = 0;
    reg left_pwm_high = 0;
    reg right_pwm_high = 0;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            pwm_counter <= 0;
            left_active_duty <= 0;
            right_active_duty <= 0;
            left_pwm_high <= 0;
            right_pwm_high <= 0;
        end else if (run_mask == 0) begin
            pwm_counter <= 0;
            left_active_duty <= 0;
            right_active_duty <= 0;
            left_pwm_high <= 0;
            right_pwm_high <= 0;
        end else begin
            if (pwm_counter == PWM_CYCLES - 1)
                pwm_counter <= 0;
            else
                pwm_counter <= pwm_counter + 1'b1;
            if (!run_mask[0])
                left_active_duty <= 0;
            else if (pwm_counter == PWM_CYCLES - 1)
                left_active_duty <= left_duty;
            if (!run_mask[1])
                right_active_duty <= 0;
            else if (pwm_counter == PWM_CYCLES - 1)
                right_active_duty <= right_duty;
            left_pwm_high <= run_mask[0] && pwm_counter < left_active_duty;
            right_pwm_high <= run_mask[1] && pwm_counter < right_active_duty;
        end
    end

    assign left_in1 = reset_n && run_mask[0] && left_pwm_high;
    assign right_in1 = reset_n && run_mask[1] && right_pwm_high;
    assign left_in2 = 1'b0;
    assign right_in2 = 1'b0;
    assign camera_reset_n = 1'b0;

    reg [31:0] heartbeat_counter = 0;
    reg heartbeat = 0;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            heartbeat_counter <= 0;
            heartbeat <= 0;
        end else if (heartbeat_counter == CLK_HZ / 2 - 1) begin
            heartbeat_counter <= 0;
            heartbeat <= ~heartbeat;
        end else
            heartbeat_counter <= heartbeat_counter + 1'b1;
    end
    wire maximum_duty = (run_mask[0] && left_active_duty == PWM_CYCLES) ||
                        (run_mask[1] && right_active_duty == PWM_CYCLES);
    assign led = {heartbeat, maximum_duty, (reset_n && run_mask == 0), right_seen,
                  left_seen, run_mask[1], run_mask[0], reset_n};
endmodule
`default_nettype wire
