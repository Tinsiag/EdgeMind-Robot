`timescale 1ns/1ps
`default_nettype none
module wheel_pi_controller #(
    parameter integer OUTPUT_LIMIT = 1000,
    parameter integer RAMP_LIMIT = 100
)(
    input wire clk,
    input wire rstn,
    input wire update,
    input wire enable,
    input wire signed [31:0] target_speed,
    input wire signed [31:0] measured_speed,
    input wire [15:0] output_limit,
    input wire [15:0] ramp_limit,
    output reg signed [31:0] command,
    output reg signed [31:0] applied_target
);
    reg signed [15:0] target_q, measured_q, integral_q, error_q;
    reg signed [16:0] next_integral;
    reg signed [17:0] raw_q;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin
            command<=0; applied_target<=0; target_q<=0; measured_q<=0; integral_q<=0; error_q<=0;
        end else if (!enable) begin
            command<=0; applied_target<=0; target_q<=0; measured_q<=0; integral_q<=0; error_q<=0;
        end else if (update) begin
            target_q <= target_speed[15:0];
            measured_q <= measured_speed[15:0];
            if (target_speed[15:0] > applied_target[15:0] + ramp_limit)
                applied_target <= applied_target + ramp_limit;
            else if (target_speed[15:0] < applied_target[15:0] - ramp_limit)
                applied_target <= applied_target - ramp_limit;
            else applied_target <= target_speed;
            error_q <= applied_target[15:0] - measured_speed[15:0];
            if (target_speed == 0) integral_q <= 0;
            else begin
                next_integral = integral_q + (error_q >>> 4);
                if (next_integral > output_limit) integral_q <= output_limit;
                else if (next_integral < -$signed(output_limit)) integral_q <= -$signed(output_limit);
                else integral_q <= next_integral[15:0];
            end
            raw_q = error_q + integral_q;
            if (raw_q > output_limit) command <= output_limit;
            else if (raw_q < -$signed(output_limit)) command <= -$signed(output_limit);
            else command <= raw_q;
        end
    end
endmodule
`default_nettype wire
