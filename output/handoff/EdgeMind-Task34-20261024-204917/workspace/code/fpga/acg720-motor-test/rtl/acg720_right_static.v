`timescale 1ns/1ps
`default_nettype none

// A71C: continuous right-channel LOGIC probe. VM MUST stay disconnected.
// User-requested fixed outputs, independent of buttons, clock and timers:
// RAIN1 = F13 / P7-7 / R-5 = 1; RAIN2 = F14 / P7-8 / R-6 = 0.
// This is not a motor-run build. S0 does not gate these fixed outputs.
module acg720_right_static #(
    parameter integer CLK_HZ = 50000000
)(
    input wire clk, stop_n, left_key_n, right_key_n,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2, camera_reset_n,
    output wire [7:0] led
);
    assign right_in1 = 1'b1;
    assign right_in2 = 1'b0;
    assign left_in1 = 1'b0;
    assign left_in2 = 1'b0;
    assign camera_reset_n = 1'b0;

    // The inputs are retained as status indicators only, keeping the common
    // reviewed 21-port constraint set. None can change the fixed motor pins.
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
    // D2 steady on, D1 off. D0=S0 released; D3/D4=AB level ORs;
    // D5/D6=raw S1/S2 pressed; D7=heartbeat. No encoder motion inference.
    assign led = {heartbeat, ~right_key_n, ~left_key_n,
                  right_enc_a | right_enc_b, left_enc_a | left_enc_b,
                  right_in1, left_in1, stop_n};
endmodule
`default_nettype wire
