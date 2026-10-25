`timescale 1ns/1ps
`default_nettype none

// A71D: continuous left-channel LOGIC probe. VM MUST stay disconnected.
// LAIN1 = A18 / P7-5 / L-1 = 1; LAIN2 = A19 / P7-6 / L-2 = 0.
// Both right-channel controls stay low. No PWM, key or timeout gating;
// S0 does not gate the fixed outputs. This is not a motor-run build.
module acg720_left_static #(
    parameter integer CLK_HZ = 50000000
)(
    input wire clk, stop_n, left_key_n, right_key_n,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2, camera_reset_n,
    output wire [7:0] led
);
    assign left_in1 = 1'b1;
    assign left_in2 = 1'b0;
    assign right_in1 = 1'b0;
    assign right_in2 = 1'b0;
    assign camera_reset_n = 1'b0;

    // Inputs affect status indicators only, retaining the reviewed 21 ports.
    reg [31:0] heartbeat_count = 0;
    reg heartbeat = 0;
    always @(posedge clk) begin
        if (!stop_n) begin
            heartbeat_count <= 0;
            heartbeat <= 0;
        end else if (heartbeat_count == CLK_HZ / 2 - 1) begin
            heartbeat_count <= 0;
            heartbeat <= ~heartbeat;
        end else heartbeat_count <= heartbeat_count + 1'b1;
    end
    // D1 steady on, D2 off. D3/D4 show AB levels, not encoder movement.
    assign led = {heartbeat, ~right_key_n, ~left_key_n,
                  right_enc_a | right_enc_b, left_enc_a | left_enc_b,
                  right_in1, left_in1, stop_n};
endmodule
`default_nettype wire
