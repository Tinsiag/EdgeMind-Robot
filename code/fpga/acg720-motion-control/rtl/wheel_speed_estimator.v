`timescale 1ns/1ps
`default_nettype none
// Multi-cycle wheel-speed conversion. One bit of the unsigned quotient is
// produced per system clock, so the 50 MHz control clock has no long divider
// in its critical path. The result is mm/s using the supplied CPR and diameter.
module wheel_speed_estimator #(
    parameter integer SAMPLE_MS = 10
)(
    input wire clk,
    input wire rstn,
    input wire sample_tick,
    input wire signed [31:0] delta_count,
    input wire [31:0] cpr,
    input wire [31:0] diameter_mm,
    output reg signed [31:0] speed_mm_s,
    output reg valid
);
    reg busy, sign_q;
    reg [5:0] bit_index;
    reg [31:0] dividend, divisor, quotient;
    reg [32:0] remainder;
    reg [31:0] quotient_next;
    reg signed [63:0] numerator;
    reg [63:0] denominator;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin
            speed_mm_s <= 0; valid <= 0; busy <= 0; sign_q <= 0;
            bit_index <= 0; dividend <= 0; divisor <= 0; quotient <= 0;
            quotient_next <= 0; remainder <= 0;
        end else begin
            valid <= 0;
            if (sample_tick && !busy) begin
                if ((cpr != 0) && (diameter_mm != 0)) begin
                    numerator = (delta_count < 0 ? -delta_count : delta_count) * diameter_mm * 3142;
                    denominator = cpr * SAMPLE_MS;
                    dividend <= numerator[31:0];
                    divisor <= denominator[31:0];
                    quotient <= 0; quotient_next <= 0; remainder <= 0;
                    bit_index <= 0; sign_q <= (delta_count < 0); busy <= 1;
                end else speed_mm_s <= 0;
            end else if (busy) begin
                remainder = {remainder[31:0], dividend[31]};
                dividend <= {dividend[30:0], 1'b0};
                if (remainder >= divisor) begin
                    remainder = remainder - divisor;
                    quotient_next = {quotient[30:0], 1'b1};
                end else quotient_next = {quotient[30:0], 1'b0};
                quotient <= quotient_next;
                if (bit_index == 31) begin
                    busy <= 0;
                    speed_mm_s <= sign_q ? -$signed(quotient_next) : $signed(quotient_next);
                    valid <= 1;
                end else bit_index <= bit_index + 1'b1;
            end
        end
    end
endmodule
`default_nettype wire
