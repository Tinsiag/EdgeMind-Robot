`timescale 1ns/1ps
`default_nettype none

// A71A: unloaded bridge-voltage measurement ONLY. Disconnect BOTH motors.
// S1 holds left IN1 high; S2 holds right IN1 high. No PWM or UART.
// Release / both keys / S0 inhibits immediately; a hold expires within 2 s.
// Every attempt requires both keys released and debounced before another start.
module acg720_bridge_probe #(
    parameter integer CLK_HZ = 50000000,
    parameter integer STARTUP_MS = 100,
    parameter integer DEBOUNCE_MS = 20,
    parameter integer PROBE_MS = 2000
)(
    input wire clk, stop_n, left_key_n, right_key_n,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2, camera_reset_n,
    output wire [7:0] led
);
    localparam integer MS_CYCLES = CLK_HZ / 1000;
    // Testbenches may shorten the hold; no build parameter may exceed 2 s.
    localparam integer LIMITED_MS = PROBE_MS < 1 ? 1 : (PROBE_MS > 2000 ? 2000 : PROBE_MS);
    localparam integer PROBE_CYCLES = MS_CYCLES * LIMITED_MS;
    localparam integer CW = $clog2(PROBE_CYCLES + 1);

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
                if (startup_count == MS_CYCLES * STARTUP_MS - 1)
                    startup_done <= 1;
                else startup_count <= startup_count + 1'b1;
            end
            reset_release <= {reset_release[0], startup_done};
        end
    end
    wire ready = stop_n && reset_release[1];
    wire [1:0] raw_keys = {~right_key_n, ~left_key_n};
    (* syn_preserve = 1 *) reg [1:0] key_meta = 0, key_sync = 0;
    (* syn_preserve = 1 *) reg [3:0] enc_meta = 0, enc_sync = 0;
    reg [31:0] ms_count = 0;
    wire ms_tick = ms_count == MS_CYCLES - 1;
    reg [1:0] candidate = 0, debounced = 0;
    reg [31:0] debounce_count = 0;
    always @(posedge clk or negedge ready) begin
        if (!ready) begin
            key_meta <= 0; key_sync <= 0;
            enc_meta <= 0; enc_sync <= 0;
            ms_count <= 0; candidate <= 0; debounced <= 0; debounce_count <= 0;
        end else begin
            key_meta <= raw_keys;
            key_sync <= key_meta;
            enc_meta <= {right_enc_b, right_enc_a, left_enc_b, left_enc_a};
            enc_sync <= enc_meta;
            if (ms_tick) begin
                ms_count <= 0;
                if (key_sync != candidate) begin
                    candidate <= key_sync;
                    debounce_count <= 0;
                end else if (key_sync == debounced) debounce_count <= 0;
                else if (debounce_count == DEBOUNCE_MS - 1) begin
                    debounced <= key_sync;
                    debounce_count <= 0;
                end else debounce_count <= debounce_count + 1'b1;
            end else ms_count <= ms_count + 1'b1;
        end
    end

    reg armed = 0;
    reg [31:0] release_count = 0;
    reg [1:0] run_mask = 0;
    reg [CW-1:0] probe_count = 0;
    reg timed_out = 0, rejected = 0;
    always @(posedge clk or negedge ready) begin
        if (!ready) begin
            armed <= 0; release_count <= 0; run_mask <= 0;
            probe_count <= 0; timed_out <= 0; rejected <= 0;
        end else if (raw_keys == 2'b11 || key_sync == 2'b11) begin
            // A chord cannot turn into an attempt on whichever key remains.
            armed <= 0; release_count <= 0; run_mask <= 0;
            probe_count <= 0; rejected <= 1;
        end else if (run_mask != 0) begin
            armed <= 0;
            release_count <= 0;
            if (raw_keys != run_mask) begin
                run_mask <= 0;
                probe_count <= 0;
            end else if (probe_count == PROBE_CYCLES - 1) begin
                run_mask <= 0;
                probe_count <= 0;
                timed_out <= 1;
            end else probe_count <= probe_count + 1'b1;
        end else begin
            probe_count <= 0;
            if (raw_keys == 0 && key_sync == 0 && debounced == 0) begin
                if (ms_tick && !armed) begin
                    if (release_count == DEBOUNCE_MS - 1) begin
                        armed <= 1;
                        release_count <= 0;
                    end else release_count <= release_count + 1'b1;
                end
            end else begin
                release_count <= 0;
                if (armed && (debounced == 2'b01 || debounced == 2'b10) &&
                    raw_keys == debounced && key_sync == debounced) begin
                    run_mask <= debounced;
                    armed <= 0;
                    timed_out <= 0;
                    rejected <= 0;
                end
            end
        end
    end

    // Raw pins gate off without waiting for debounce, synchronizers or a clock.
    assign left_in1 = ready && run_mask == 2'b01 && raw_keys == 2'b01;
    assign right_in1 = ready && run_mask == 2'b10 && raw_keys == 2'b10;
    assign left_in2 = 1'b0;
    assign right_in2 = 1'b0;
    assign camera_reset_n = 1'b0;

    reg [31:0] heartbeat_count = 0;
    reg heartbeat = 0;
    always @(posedge clk or negedge ready) begin
        if (!ready) begin heartbeat_count <= 0; heartbeat <= 0; end
        else if (heartbeat_count == CLK_HZ / 2 - 1) begin
            heartbeat_count <= 0;
            heartbeat <= ~heartbeat;
        end else heartbeat_count <= heartbeat_count + 1'b1;
    end
    // D3/D4 are synchronized AB level ORs, not encoder faults or movement proof.
    assign led = {heartbeat, rejected, timed_out, |enc_sync[3:2], |enc_sync[1:0],
                  right_in1, left_in1, ready};
endmodule
`default_nettype wire
