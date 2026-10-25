`timescale 1ns/1ps
`default_nettype none
module rotate_controller(
    input wire clk,
    input wire rstn,
    input wire start,
    input wire cancel,
    input wire signed [31:0] angle_mdeg,
    input wire [31:0] max_speed,
    input wire signed [31:0] left_count,
    input wire signed [31:0] right_count,
    input wire signed [31:0] left_speed,
    input wire signed [31:0] right_speed,
    input wire [31:0] counts_per_degree_q16,
    input wire [31:0] tolerance_counts,
    output reg active,
    output reg done,
    output reg signed [31:0] left_target,
    output reg signed [31:0] right_target
);
    reg [31:0] saved_max_speed;
    reg signed [31:0] start_l, start_r, target_delta;
    reg signed [63:0] target_calc;
    reg signed [31:0] err_l, err_r, mag_l, mag_r, speed_cmd;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin saved_max_speed<=0; active <= 0; done <= 0; left_target <= 0; right_target <= 0; start_l <= 0; start_r <= 0; target_delta <= 0; end
        else begin
            done <= 0;
            if (cancel) begin
                active<=0; done<=0; left_target<=0; right_target<=0;
            end else if (start && !active) begin
                saved_max_speed <= max_speed;
                start_l <= left_count; start_r <= right_count;
                // counts_per_degree_q16 is configured as counts per mdeg in Q16.
                target_calc = ($signed(angle_mdeg) * $signed({1'b0,counts_per_degree_q16})) >>> 16;
                target_delta <= target_calc[31:0]; active <= 1;
            end else if (active) begin
                err_l = -target_delta - (left_count - start_l);
                err_r = target_delta - (right_count - start_r);
                mag_l = err_l < 0 ? -err_l : err_l;
                mag_r = err_r < 0 ? -err_r : err_r;
                if ((mag_l <= tolerance_counts) && (mag_r <= tolerance_counts) &&
                    ((left_speed < 20) && (left_speed > -20)) && ((right_speed < 20) && (right_speed > -20))) begin
                    left_target <= 0; right_target <= 0; active <= 0; done <= 1;
                end else begin
                    speed_cmd = saved_max_speed > 32767 ? 32767 : $signed(saved_max_speed);
                    if (mag_l < speed_cmd) speed_cmd = mag_l;
                    if (mag_r < speed_cmd) speed_cmd = mag_r;
                    if (speed_cmd < 20) speed_cmd = 20;
                    left_target <= err_l < 0 ? -speed_cmd : speed_cmd;
                    right_target <= err_r < 0 ? -speed_cmd : speed_cmd;
                end
            end else begin left_target <= 0; right_target <= 0; end
        end
    end
endmodule
`default_nettype wire
