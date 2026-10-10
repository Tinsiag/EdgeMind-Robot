`timescale 1ns/1ps
`default_nettype none

// Standalone, manually triggered AT8236 test. Never starts on configuration.
// S1: left only; S2: right only. Holding a button never repeats a test.
// IN1 = PWM, IN2 = 0; 00 coasts. This is bridge polarity, not vehicle forward.
module acg720_motor_test #(
    parameter integer CLK_HZ = 50000000,
    parameter integer PWM_HZ = 20000,
    parameter integer STARTUP_MS = 100,
    parameter integer DEBOUNCE_MS = 20,
    parameter integer RUN_MS = 2000,
    parameter integer RAMP_MS = 200,
    parameter integer DUTY_PERCENT = 25
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
    localparam integer PWM_WIDTH = $clog2(PWM_CYCLES);
    localparam integer MS_WIDTH = $clog2(MS_CYCLES + 1);
    localparam integer DEBOUNCE_WIDTH = $clog2(DEBOUNCE_MS + 1);
    localparam integer RUN_WIDTH = $clog2(RUN_MS + 1);

    // Gowin synthesizes these initial values into configuration/GSR state.
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
            // Assert immediately, release only after two clock edges.
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

    reg armed = 0;
    reg [DEBOUNCE_WIDTH-1:0] release_count = 0;
    reg [1:0] run_mask = 0;
    reg [RUN_WIDTH-1:0] elapsed_ms = 0;
    reg completed = 0;
    reg rejected = 0;
    reg left_seen = 0;
    reg right_seen = 0;
    // Wait for BOTH raw-synchronized and debounced keys to be released.
    // Thus a key held during configuration/reset cannot become a start event.
    wire start_event = reset_n && run_mask == 0 && armed &&
        ((key_pressed == 2'b01 && key_sync == 2'b01) ||
         (key_pressed == 2'b10 && key_sync == 2'b10));
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            armed <= 0;
            release_count <= 0;
            run_mask <= 0;
            elapsed_ms <= 0;
            completed <= 0;
            rejected <= 0;
            left_seen <= 0;
            right_seen <= 0;
        end else begin
            // Ignore the initial sampling of a static high encoder level.
            if (encoder_valid[2] && |(enc_sync[1:0] ^ enc_previous[1:0])) left_seen <= 1;
            if (encoder_valid[2] && |(enc_sync[3:2] ^ enc_previous[3:2])) right_seen <= 1;
            if (run_mask != 0) begin
                armed <= 0;
                release_count <= 0;
                if (ms_tick) begin
                    if (elapsed_ms == RUN_MS - 1) begin
                        run_mask <= 0;
                        completed <= 1;
                    end else
                        elapsed_ms <= elapsed_ms + 1'b1;
                end
            end else if (key_sync == 2'b11) begin
                // Reject chords before either key can finish debouncing.
                armed <= 0;
                release_count <= 0;
                rejected <= 1;
            end else if (start_event) begin
                run_mask <= key_pressed;
                elapsed_ms <= 0;
                armed <= 0;
                release_count <= 0;
                completed <= 0;
                rejected <= 0;
                left_seen <= 0;
                right_seen <= 0;
            end else if (key_sync == 0 && key_pressed == 0) begin
                if (ms_tick && !armed) begin
                    if (release_count == DEBOUNCE_MS - 1) begin
                        armed <= 1;
                        release_count <= 0;
                    end else
                        release_count <= release_count + 1'b1;
                end
            end else
                release_count <= 0;
        end
    end

    // Default profile remains 10 -> 15 -> 20 -> 25 percent.
    // The short 50% diagnostic uses 10 -> 25 -> 40 -> 50 percent.
    // DUTY_PERCENT is a build-time parameter; keys cannot increase it.
    wire [PWM_WIDTH-1:0] duty_cycles =
        elapsed_ms < RAMP_MS / 4 ? (PWM_CYCLES * 10 / 100) :
        elapsed_ms < RAMP_MS / 2 ? (PWM_CYCLES * (DUTY_PERCENT == 50 ? 25 : 15) / 100) :
        elapsed_ms < RAMP_MS     ? (PWM_CYCLES * (DUTY_PERCENT == 50 ? 40 : 20) / 100) :
                                   (PWM_CYCLES * DUTY_PERCENT / 100);
    reg [PWM_WIDTH-1:0] pwm_counter = 0;
    reg pwm_high = 0;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            pwm_counter <= 0;
            pwm_high <= 0;
        end else if (run_mask == 0) begin
            pwm_counter <= 0;
            pwm_high <= 0;
        end else begin
            if (pwm_counter == PWM_CYCLES - 1)
                pwm_counter <= 0;
            else
                pwm_counter <= pwm_counter + 1'b1;
            pwm_high <= pwm_counter < duty_cycles;
        end
    end
    // S0 additionally gates the physical outputs, independent of clock edges.
    assign left_in1 = reset_n && run_mask[0] && pwm_high;
    assign right_in1 = reset_n && run_mask[1] && pwm_high;
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
    assign led = {heartbeat, rejected, completed, right_seen, left_seen,
                  run_mask[1], run_mask[0], reset_n};
endmodule
`default_nettype wire
