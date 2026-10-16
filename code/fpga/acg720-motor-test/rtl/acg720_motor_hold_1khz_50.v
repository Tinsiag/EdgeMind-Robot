`timescale 1ns/1ps
`default_nettype none

// A71B: manual single-wheel test. IN1=1 kHz PWM, IN2=0 (coast).
// Hold S1/S2 for left/right. Release, S0 or a chord inhibits immediately.
// Ramp 10 -> 25 -> 40 -> 50%; total hold is capped at 1000 ms.
// The bridge-probe controller is reused ONLY as an internal enable/timer;
// its static outputs never connect directly to physical motor pins here.
// Confirmed 2026-10-15: L1/2 = P7-5/6 = A18/A19;
// R5/6 = P7-7/8 = F13/F14. R is the six-wire header in the photo.
module acg720_motor_hold_1khz_50 #(
    parameter integer CLK_HZ = 50000000,
    parameter integer STARTUP_MS = 100,
    parameter integer DEBOUNCE_MS = 20,
    parameter integer RUN_MS = 1000
)(
    input wire clk, stop_n, left_key_n, right_key_n,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2, camera_reset_n,
    output wire [7:0] led
);
    localparam integer LIMITED_MS = RUN_MS < 1 ? 1 : (RUN_MS > 1000 ? 1000 : RUN_MS);
    localparam integer MS_CYCLES = CLK_HZ / 1000;
    localparam integer PWM_CYCLES = CLK_HZ / 1000;
    localparam integer PWM_WIDTH = $clog2(PWM_CYCLES + 1);
    localparam integer AGE_WIDTH = $clog2(MS_CYCLES * 1000 + 1);
    wire left_enable, right_enable;
    wire [7:0] control_led;
    acg720_bridge_probe #(
        .CLK_HZ(CLK_HZ), .STARTUP_MS(STARTUP_MS),
        .DEBOUNCE_MS(DEBOUNCE_MS), .PROBE_MS(LIMITED_MS)
    ) hold_control (
        .clk(clk), .stop_n(stop_n), .left_key_n(left_key_n), .right_key_n(right_key_n),
        .left_enc_a(left_enc_a), .left_enc_b(left_enc_b),
        .right_enc_a(right_enc_a), .right_enc_b(right_enc_b),
        .left_in1(left_enable), .right_in1(right_enable),
        .left_in2(), .right_in2(), .camera_reset_n(), .led(control_led)
    );
    wire active = left_enable || right_enable;
    reg [AGE_WIDTH-1:0] age_cycles = 0;
    reg [PWM_WIDTH-1:0] pwm_count = 0;
    // Steps change only on 1 ms boundaries, hence complete PWM periods.
    wire [PWM_WIDTH-1:0] duty_cycles =
        age_cycles < MS_CYCLES * 50  ? PWM_CYCLES * 10 / 100 :
        age_cycles < MS_CYCLES * 100 ? PWM_CYCLES * 25 / 100 :
        age_cycles < MS_CYCLES * 200 ? PWM_CYCLES * 40 / 100 :
                                      PWM_CYCLES * 50 / 100;
    always @(posedge clk or negedge stop_n) begin
        if (!stop_n) begin
            age_cycles <= 0; pwm_count <= 0;
        end else if (!active) begin
            age_cycles <= 0; pwm_count <= 0;
        end else begin
            age_cycles <= age_cycles + 1'b1;
            if (pwm_count == PWM_CYCLES - 1) pwm_count <= 0;
            else pwm_count <= pwm_count + 1'b1;
        end
    end
    // Raw key / stop gating is already in the enables and bypasses PWM state.
    wire pwm_high = pwm_count < duty_cycles;
    assign left_in1 = left_enable && pwm_high;
    assign right_in1 = right_enable && pwm_high;
    assign left_in2 = 1'b0;
    assign right_in2 = 1'b0;
    assign camera_reset_n = 1'b0;
    // Four legal AB transitions during an attempt latch D3/D4. A static high
    // level or an illegal two-bit jump cannot look like encoder activity.
    (* syn_preserve = 1 *) reg [3:0] motion_meta = 0, motion_sync = 0;
    reg [3:0] previous_ab = 0;
    reg [1:0] previous_enable = 0, encoder_seen = 0;
    reg [2:0] left_edges = 0, right_edges = 0;
    function legal_edge;
        input [1:0] previous_state, current_state;
        begin
            case ({previous_state, current_state})
                4'b0001, 4'b0111, 4'b1110, 4'b1000,
                4'b0010, 4'b1011, 4'b1101, 4'b0100: legal_edge = 1'b1;
                default: legal_edge = 1'b0;
            endcase
        end
    endfunction
    always @(posedge clk or negedge stop_n) begin
        if (!stop_n) begin
            motion_meta <= 0; motion_sync <= 0; previous_ab <= 0;
            previous_enable <= 0; encoder_seen <= 0;
            left_edges <= 0; right_edges <= 0;
        end else begin
            motion_meta <= {right_enc_b, right_enc_a, left_enc_b, left_enc_a};
            motion_sync <= motion_meta;
            previous_ab <= motion_sync;
            previous_enable <= {right_enable, left_enable};
            if (active && previous_enable == 0) begin
                encoder_seen <= 0; left_edges <= 0; right_edges <= 0;
            end else begin
                if (left_enable && !encoder_seen[0] &&
                    legal_edge(previous_ab[1:0], motion_sync[1:0])) begin
                    if (left_edges == 3) encoder_seen[0] <= 1;
                    else left_edges <= left_edges + 1'b1;
                end
                if (right_enable && !encoder_seen[1] &&
                    legal_edge(previous_ab[3:2], motion_sync[3:2])) begin
                    if (right_edges == 3) encoder_seen[1] <= 1;
                    else right_edges <= right_edges + 1'b1;
                end
            end
        end
    end
    // D1/D2 are steady enables; D3/D4 retain activity until the next attempt.
    // Activity does not establish direction, speed, or successful wheel motion.
    assign led = {control_led[7:5], encoder_seen, control_led[2:0]};
endmodule
`default_nettype wire
