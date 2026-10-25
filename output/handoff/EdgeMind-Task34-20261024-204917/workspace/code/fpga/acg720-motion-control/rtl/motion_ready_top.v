`timescale 1ns/1ps
`default_nettype none
// A722: calibrated UART profile; user-requested illegal-AB stop bypass.
// STOP, disarm, command TTL and no-feedback fault remain active.
module motion_ready_top(
    input wire clk, stop_n, uart_rx,
    output wire uart_tx,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2,
    output wire [7:0] led
);
    motion_top #(.PWM_HZ(1000), .PI_LIMIT_DEFAULT(512), .RAMP_LIMIT_DEFAULT(50),
                 .CALIBRATED_DEFAULTS(1), .ENCODER_FAULT_ENABLE(0)) controller(
        .clk(clk), .stop_n(stop_n), .uart_rx(uart_rx), .uart_tx(uart_tx),
        .left_enc_a(left_enc_a), .left_enc_b(left_enc_b),
        .right_enc_a(right_enc_a), .right_enc_b(right_enc_b),
        .left_in1(left_in1), .left_in2(left_in2),
        .right_in1(right_in1), .right_in2(right_in2), .led(led)
    );
endmodule
`default_nettype wire
