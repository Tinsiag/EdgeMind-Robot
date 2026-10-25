`timescale 1ns/1ps
`default_nettype none
module at8236_motor_driver #(
    parameter integer PWM_HZ = 20000,
    parameter integer CLK_HZ = 50000000,
    parameter integer PWM_LIMIT = 1024
)(
    input wire clk,
    input wire rstn,
    input wire enable,
    input wire signed [31:0] command,
    output reg in1,
    output reg in2,
    output reg [31:0] pwm_abs
);
    localparam integer PERIOD = CLK_HZ / PWM_HZ;
    localparam integer PW = $clog2(PERIOD);
    reg [PW-1:0] pwm_count;
    reg direction;
    reg dead;
    reg desired_direction;
    reg [PW-1:0] duty;
    reg [63:0] magnitude;
    reg [63:0] duty_calc;
    always @* begin
        desired_direction = command < 0;
        magnitude = command < 0 ? -command : command;
        if (magnitude > PWM_LIMIT) magnitude = PWM_LIMIT;
        duty_calc = (magnitude * PERIOD) >> 10;
        duty = duty_calc[PW-1:0];
    end
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin pwm_count <= 0; direction <= 0; dead <= 0; in1 <= 0; in2 <= 0; pwm_abs <= 0; end
        else begin
            if (pwm_count == PERIOD-1) begin
                pwm_count <= 0;
                if (!enable || command == 0) begin dead <= 0; pwm_abs <= 0; end
                else if (desired_direction != direction) begin direction <= desired_direction; dead <= 1; pwm_abs <= 0; end
                else begin dead <= 0; pwm_abs <= magnitude[31:0]; end
            end else pwm_count <= pwm_count + 1'b1;
            if (!enable || command == 0 || dead) begin in1 <= 0; in2 <= 0; end
            else if (direction == 0) begin in1 <= pwm_count < duty; in2 <= 0; end
            else begin in1 <= 0; in2 <= pwm_count < duty; end
        end
    end
endmodule
`default_nettype wire
