`timescale 1ns/1ps
`default_nettype none
// Outer motion feedback for the chip-local and autonomous personalities.
//
// a741_pi already closes each wheel's speed loop.  This block adds the
// differential-drive outer loop that keeps a straight command straight when
// the two motors or the floor load differ.  It deliberately does not alter
// opposite-sign wheel commands (in-place turns), because those commands are
// supposed to create yaw.  The correction is bounded in the same signed
// target units used by a741_pi and is updated at the 100 Hz control tick.
module a741_motion_feedback(
    input wire clk,rst_n,tick,enable,imu_valid,
    input wire signed [31:0] target_l,target_r,left_speed,right_speed,
    input wire signed [15:0] yaw,
    output reg signed [31:0] corrected_l,corrected_r,
    output reg heading_active,
    output reg signed [15:0] heading_error,
    output reg signed [15:0] speed_error
);
    reg straight_q;
    reg target_negative_q;
    reg signed [15:0] yaw_origin;

    wire straight = target_l!=0 && target_r!=0 &&
        (target_l[31] == target_r[31]);
    wire target_negative = target_l[31];
    wire signed [15:0] wrapped_yaw_delta = yaw-yaw_origin;
    wire signed [16:0] yaw_delta = $signed({wrapped_yaw_delta[15],wrapped_yaw_delta});
    wire signed [16:0] yaw_limited = yaw_delta>17'sd1280 ? 17'sd1280 :
        yaw_delta < -17'sd1280 ? -17'sd1280 : yaw_delta;
    // 64 raw yaw units per target unit, bounded to +/-20.
    wire signed [10:0] heading_correction = yaw_limited >>> 6;
    wire signed [32:0] speed_delta =
        $signed({left_speed[31],left_speed})-
        $signed({right_speed[31],right_speed});
    wire signed [32:0] speed_limited = speed_delta>33'sd256 ? 33'sd256 :
        speed_delta < -33'sd256 ? -33'sd256 : speed_delta;
    // 16 speed units per target unit, bounded to +/-16.
    wire signed [10:0] sync_correction = speed_limited >>> 4;
    // Reversing reverses the wheel-difference-to-yaw sign.  The speed
    // synchronizer remains signed and therefore works in both directions.
    wire signed [11:0] heading_term = target_negative ?
        -$signed({heading_correction[10],heading_correction}) :
        $signed({heading_correction[10],heading_correction});
    wire signed [12:0] correction_l =
        $signed({heading_term[11],heading_term})-
        $signed({sync_correction[10],sync_correction});
    wire signed [12:0] correction_r =
        -$signed({heading_term[11],heading_term})+
        $signed({sync_correction[10],sync_correction});
    wire signed [33:0] raw_l = $signed({target_l[31],target_l})+
        $signed({correction_l[12],correction_l});
    wire signed [33:0] raw_r = $signed({target_r[31],target_r})+
        $signed({correction_r[12],correction_r});

    function signed [31:0] bounded_target;
        input signed [33:0] value;
        begin
            if(value>34'sd400) bounded_target=32'sd400;
            else if(value < -34'sd400) bounded_target=-32'sd400;
            else bounded_target=value[31:0];
        end
    endfunction

    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            straight_q<=0;target_negative_q<=0;yaw_origin<=0;
            corrected_l<=0;corrected_r<=0;heading_active<=0;
            heading_error<=0;speed_error<=0;
        end else if(!enable) begin
            straight_q<=0;target_negative_q<=0;
            corrected_l<=0;corrected_r<=0;heading_active<=0;
            heading_error<=0;speed_error<=0;
        end else if(!straight || !imu_valid) begin
            // A stop or an in-place turn must pass through immediately.  A
            // missing IMU is also fail-open here only because a741_motion's
            // independent imu_fault gate removes motor_enable in that case.
            straight_q<=0;target_negative_q<=target_negative;
            corrected_l<=target_l;corrected_r<=target_r;heading_active<=0;
            heading_error<=0;speed_error<=0;
        end else if(tick) begin
            if(!straight_q || target_negative_q!=target_negative) begin
                // Start every straight segment from its measured heading.
                yaw_origin<=yaw;straight_q<=1;target_negative_q<=target_negative;
                corrected_l<=target_l;corrected_r<=target_r;
                heading_active<=1;heading_error<=0;speed_error<=0;
            end else begin
                corrected_l<=bounded_target(raw_l);
                corrected_r<=bounded_target(raw_r);
                heading_active<=1;
                heading_error<=yaw_limited[15:0];
                speed_error<=speed_limited[15:0];
            end
        end
endmodule
`default_nettype wire
