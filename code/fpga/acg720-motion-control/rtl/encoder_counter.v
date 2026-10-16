`timescale 1ns/1ps
`default_nettype none
module encoder_counter #(
    parameter integer TIMEOUT_MS = 200
)(
    input wire clk,
    input wire rstn,
    input wire signed [1:0] step,
    input wire invalid_step,
    input wire sample_tick,
    input wire monitor_enable,
    output reg signed [31:0] count,
    output reg signed [31:0] delta,
    output reg [31:0] invalid_count,
    output reg feedback_timeout
);
    reg signed [31:0] sample_base;
    localparam integer TIMEOUT_SAMPLES = (TIMEOUT_MS < 10) ? 1 : (TIMEOUT_MS / 10);
    reg [31:0] idle_samples;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin count <= 0; delta <= 0; sample_base <= 0; invalid_count <= 0; idle_samples <= 0; feedback_timeout <= 0; end
        else begin
            if (step == 1) count <= count + 1'b1;
            else if (step == -1) count <= count - 1'b1;
            if (invalid_step) invalid_count <= invalid_count + 1'b1;
            // Sample even when an edge coincides with sample_tick.
            if (sample_tick) begin
                delta <= count - sample_base;
                sample_base <= count;
            end
            // Start a fresh feedback window only when this wheel is commanded.
            if (!monitor_enable || step != 0) begin idle_samples <= 0; feedback_timeout <= 0; end
            else if (sample_tick) begin
                if (idle_samples < TIMEOUT_SAMPLES) idle_samples <= idle_samples + 1'b1;
                if (idle_samples >= TIMEOUT_SAMPLES-1) feedback_timeout <= 1;
            end
        end
    end
endmodule
`default_nettype wire
