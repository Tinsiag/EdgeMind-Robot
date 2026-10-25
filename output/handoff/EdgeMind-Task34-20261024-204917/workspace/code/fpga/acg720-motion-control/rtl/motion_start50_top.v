`timescale 1ns/1ps
`default_nettype none
// A721: UART closed-loop bench variant based on A712's 1 kHz/50% envelope.
// PI remains closed-loop; this does not reproduce A712's open-loop duty ramp.
module motion_start50_top(
    input wire clk, stop_n, uart_rx,
    output wire uart_tx,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2,
    output wire [7:0] led
);
    motion_top #(.PWM_HZ(1000), .PI_LIMIT_DEFAULT(512), .RAMP_LIMIT_DEFAULT(50)) controller(
        .clk(clk), .stop_n(stop_n), .uart_rx(uart_rx), .uart_tx(uart_tx),
        .left_enc_a(left_enc_a), .left_enc_b(left_enc_b),
        .right_enc_a(right_enc_a), .right_enc_b(right_enc_b),
        .left_in1(left_in1), .left_in2(left_in2),
        .right_in1(right_in1), .right_in2(right_in2), .led(led)
    );
endmodule
`default_nettype wire
