`timescale 1ns/1ps
`default_nettype none
// Every speed and PWM ramp step is gated by the 100 Hz update, not clk.
module a741_pi #(parameter TARGET_LIMIT_ENABLED=0)(
    input wire clk,rst_n,tick,enable,
    input wire signed [31:0] target,measured,
    input wire [9:0] target_limit,
    input wire [15:0] speed_step,pwm_step,limit,
    output reg signed [31:0] applied,command
);
    localparam IDLE=0,PREPARE=1,RAMP=2,ERROR=3,MAGNITUDE=4,QUOTIENT=5,
        ADD_I=6,CLAMP_I=7,DESIRED=8,CLAMP=9,POLARITY=10,PWM_DIFF=11,
        PWM_RAMP=12,FINAL_CAP=13,COMMIT=14,LIMIT_TARGET=15;
    reg [3:0] state;
    reg signed [31:0] target_q,measured_q,next_applied,applied_up,applied_down;
    reg signed [32:0] target_difference,error;
    reg [32:0] error_magnitude;
    reg signed [29:0] integral_delta;
    reg signed [30:0] integral_sum;
    reg signed [33:0] desired_raw;
    reg signed [10:0] integral,next_i,cap,negative_cap,desired_capped,desired_polarity,final_command;
    reg signed [16:0] ss,negative_ss;
    reg signed [10:0] target_cap;
    reg signed [11:0] ps,negative_ps,command_up,command_down,pwm_difference,desired_step;
    reg unwind,write_integral;
    wire [9:0] cap_input=limit>512 ? 10'd512:limit[9:0];
    wire [16:0] ss_input=speed_step==0 ? 17'd1:{1'b0,speed_step};
    // Both PWM endpoints lie in +/-512, so steps above 1024 are equivalent.
    wire [11:0] ps_input=pwm_step==0 ? 12'd1:pwm_step>1024 ? 12'd1024:{1'b0,pwm_step[10:0]};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            applied<=0;command<=0;integral<=0;state<=IDLE;target_q<=0;measured_q<=0;
            next_applied<=0;applied_up<=0;applied_down<=0;target_difference<=0;error<=0;
            error_magnitude<=0;integral_delta<=0;integral_sum<=0;desired_raw<=0;next_i<=0;
            cap<=0;negative_cap<=0;desired_capped<=0;desired_polarity<=0;final_command<=0;
            ss<=0;negative_ss<=0;ps<=0;negative_ps<=0;command_up<=0;command_down<=0;
            pwm_difference<=0;desired_step<=0;unwind<=0;write_integral<=0;target_cap<=0;
        end else if(!enable) begin
            applied<=0;command<=0;integral<=0;state<=IDLE;
        end else case(state)
            IDLE: if(tick) begin
                target_q<=target;measured_q<=measured;cap<=$signed({1'b0,cap_input});
                negative_cap<=-$signed({1'b0,cap_input});ss<=$signed(ss_input);negative_ss<=-$signed(ss_input);
                ps<=$signed(ps_input);negative_ps<=-$signed(ps_input);
                target_cap<=$signed({1'b0,target_limit});state<=TARGET_LIMIT_ENABLED!=0 ? LIMIT_TARGET:PREPARE;
            end
            LIMIT_TARGET:begin
                // Clamp the raw target and cap sampled together on this tick.
                // No previous-cycle target cache can reintroduce a drive pulse.
                target_q<=target_q>target_cap ? target_cap:target_q< -target_cap ? -target_cap:target_q;
                state<=PREPARE;
            end
            PREPARE: begin
                // Capture this tick before selecting ramps; no arithmetic chain spans stages.
                unwind<=(command>0 && target_q<0) || (command<0 && target_q>0) ||
                    (applied>0 && target_q<0) || (applied<0 && target_q>0) || target_q==0;
                target_difference<=$signed({target_q[31],target_q})-$signed({applied[31],applied});
                applied_up<=applied+ss;applied_down<=applied-ss;
                command_up<=$signed(command[10:0])+ps;command_down<=$signed(command[10:0])-ps;
                state<=RAMP;
            end
            RAMP: begin
                if(unwind) begin
                    if(applied>ss) next_applied<=applied_down;
                    else if(applied<negative_ss) next_applied<=applied_up;
                    else next_applied<=0;
                    if(command>ps) desired_step<=command_down;
                    else if(command<negative_ps) desired_step<=command_up;
                    else desired_step<=0;
                    next_i<=0;write_integral<=1;state<=FINAL_CAP;
                end else begin
                    if(target_difference>ss) next_applied<=applied_up;
                    else if(target_difference<negative_ss) next_applied<=applied_down;
                    else next_applied<=target_q;
                    state<=ERROR;
                end
            end
            ERROR: begin
                // Keep the full encoder feedback range; subtraction must not wrap at 32 bits.
                error<=$signed({next_applied[31],next_applied})-$signed({measured_q[31],measured_q});
                state<=MAGNITUDE;
            end
            MAGNITUDE: begin error_magnitude<=error[32] ? -error:error;state<=QUOTIENT;end
            QUOTIENT: begin
                // Magnitude division followed by sign restoration truncates toward zero.
                integral_delta<=error[32] ? -$signed({1'b0,error_magnitude[32:4]}):$signed({1'b0,error_magnitude[32:4]});
                state<=ADD_I;
            end
            ADD_I: begin integral_sum<=integral+integral_delta;state<=CLAMP_I;end
            CLAMP_I: begin
                if(integral_sum>cap) next_i<=cap;
                else if(integral_sum<negative_cap) next_i<=negative_cap;
                else next_i<=integral_sum[10:0];
                state<=DESIRED;
            end
            DESIRED: begin desired_raw<=$signed({error[32],error})+next_i;state<=CLAMP;end
            CLAMP: begin
                write_integral<=!((desired_raw>cap && error>0)||(desired_raw<negative_cap && error<0));
                if(desired_raw>cap) desired_capped<=cap;
                else if(desired_raw<negative_cap) desired_capped<=negative_cap;
                else desired_capped<=desired_raw[10:0];
                state<=POLARITY;
            end
            POLARITY: begin
                if((next_applied>=0 && desired_capped<0)||(next_applied<=0 && desired_capped>0)) desired_polarity<=0;
                else desired_polarity<=desired_capped;
                state<=PWM_DIFF;
            end
            PWM_DIFF: begin pwm_difference<=desired_polarity-$signed(command[10:0]);state<=PWM_RAMP;end
            PWM_RAMP: begin
                if(pwm_difference>ps) desired_step<=command_up;
                else if(pwm_difference<negative_ps) desired_step<=command_down;
                else desired_step<=desired_polarity;
                state<=FINAL_CAP;
            end
            FINAL_CAP: begin
                if(desired_step>cap) final_command<=cap;
                else if(desired_step<negative_cap) final_command<=negative_cap;
                else final_command<=desired_step[10:0];
                state<=COMMIT;
            end
            COMMIT: begin
                command<=final_command;applied<=next_applied;
                if(write_integral) integral<=next_i;
                state<=IDLE;
            end
            default: state<=IDLE;
        endcase
endmodule
`default_nettype wire
