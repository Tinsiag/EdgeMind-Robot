`timescale 1ns/1ps
`default_nettype none

// Manual, single-wheel startup comparison; at most 50%, for one second.
module acg720_motor_test_start50 #(
    parameter integer CLK_HZ = 50000000,
    parameter integer STARTUP_MS = 100,
    parameter integer DEBOUNCE_MS = 20,
    parameter integer RUN_MS = 1000,
    parameter integer RAMP_MS = 200
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
    acg720_motor_test #(
        .CLK_HZ(CLK_HZ), .PWM_HZ(1000), .DUTY_PERCENT(50),
        .STARTUP_MS(STARTUP_MS), .DEBOUNCE_MS(DEBOUNCE_MS),
        .RUN_MS(RUN_MS), .RAMP_MS(RAMP_MS)
    ) controller (
        .clk(clk), .stop_n(stop_n), .left_key_n(left_key_n),
        .right_key_n(right_key_n), .left_enc_a(left_enc_a),
        .left_enc_b(left_enc_b), .right_enc_a(right_enc_a),
        .right_enc_b(right_enc_b), .left_in1(left_in1),
        .left_in2(left_in2), .right_in1(right_in1),
        .right_in2(right_in2), .camera_reset_n(camera_reset_n), .led(led)
    );
endmodule
`default_nettype wire
