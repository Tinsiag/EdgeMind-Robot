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
    reg signed [15:0] integral_q;
    reg signed [16:0] target_q, measured_q, applied_q, next_target;
    reg signed [16:0] limit_q, ramp_q;
    reg signed [17:0] difference, error_q, next_integral, raw_q;
    // Clamp to a documented signed control range rather than wrapping low bits.
    function signed [16:0] speed_q;
        input signed [31:0] speed;
        begin
            if (speed > 32767) speed_q=17'sd32767;
            else if (speed < -32767) speed_q=-17'sd32767;
            else speed_q={speed[15],speed[15:0]};
        end
    endfunction
    reg [3:0] stage;
    // Spread the arithmetic over clock cycles, well within each 10 ms update.
    // All registers have explicit signed widths; disable/zero wins at every stage.
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin command<=0; applied_target<=0; integral_q<=0; stage<=0;
            target_q<=0; measured_q<=0; applied_q<=0; next_target<=0;
            limit_q<=0; ramp_q<=0; difference<=0; error_q<=0; next_integral<=0; raw_q<=0;
        end else if (!enable) begin
            command<=0; applied_target<=0; integral_q<=0; stage<=0;
        end else if (target_speed == 0) begin
            // A commanded stop still decays the PWM over a few control ticks.
            // The external STOP/timeout path disables enable and remains immediate.
            applied_target<=0; integral_q<=0; stage<=0;
            if (command > $signed({1'b0,ramp_limit})) command<=command-$signed({1'b0,ramp_limit});
            else if (command < -$signed({1'b0,ramp_limit})) command<=command+$signed({1'b0,ramp_limit});
            else command<=0;
        end else begin
            case(stage)
                0: if(update) begin
                    target_q<=speed_q(target_speed); measured_q<=speed_q(measured_speed);
                    applied_q<=speed_q(applied_target);
                    limit_q<=output_limit>1024 ? 17'sd1024 : $signed({1'b0,output_limit});
                    ramp_q<=$signed({1'b0,ramp_limit}); stage<=1;
                end
                1: begin difference<=$signed(target_q)-$signed(applied_q); stage<=2; end
                2: begin
                    if(difference>ramp_q) next_target<=applied_q+ramp_q;
                    else if(difference < -ramp_q) next_target<=applied_q-ramp_q;
                    else next_target<=target_q;
                    stage<=3;
                end
                3: begin error_q<=$signed(next_target)-$signed(measured_q); stage<=4; end
                4: begin next_integral<=$signed(integral_q)+(error_q >>> 4); stage<=5; end
                5: begin
                    if(next_integral>limit_q) next_integral<=limit_q;
                    else if(next_integral < -limit_q) next_integral<=-limit_q;
                    stage<=6;
                end
                6: begin raw_q<=error_q+next_integral; stage<=7; end
                7: begin
                    if (!((raw_q>limit_q && error_q>0) ||
                          (raw_q < -limit_q && error_q<0))) integral_q<=next_integral[15:0];
                    stage<=8;
                end
                8: begin raw_q<=error_q+$signed(integral_q); stage<=9; end
                9: begin
                    if(raw_q>limit_q) command<=limit_q;
                    else if(raw_q < -limit_q) command<=-limit_q;
                    else command<=raw_q;
                    applied_target<=next_target; stage<=0;
                end
                default: stage<=0;
            endcase
        end
    end
endmodule
`default_nettype wire
