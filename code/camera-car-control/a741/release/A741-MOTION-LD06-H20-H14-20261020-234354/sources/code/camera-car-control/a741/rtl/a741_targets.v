`timescale 1ns/1ps
`default_nettype none
// Snapshot each 100 Hz update and publish both wheel targets together.
// Arithmetic finishes in under 250 clocks; cancellation discards in-flight work.
module a741_targets(
    input wire clk,rst_n,enable,tick,cancel,
    input wire rotating,turn_braking,heading_hold,heading_positive,
    input wire signed [10:0] desired_l,desired_r,
    input wire signed [15:0] yaw,heading_origin,gz,gyro_bias,
    input wire signed [31:0] turn_target,accumulated_yaw,left_speed,right_speed,
    input wire [8:0] max_speed,turn_speed,
    input wire [5:0] speed_step,
    input wire tof_valid,input wire [31:0] clearance,
    output reg valid,braking,
    output reg signed [31:0] target_l,target_r
);
    localparam IDLE=0,NORM=1,LEFT_WAIT=2,RIGHT_START=3,RIGHT_WAIT=4,
        CORRECT=5,RECHECK=6,TOF=7,DONE=8,BRAKE_WAIT=9,BRAKE_MUL=10,
        BRAKE_DIV=11,BRAKE_DECIDE=12;
    reg [3:0] state,after_scale;
    reg signed [10:0] wl,wr,corr;
    reg signed [16:0] delta;
    reg [8:0] cap,turn_cap,peak,factor;
    reg [15:0] scale_divisor;
    reg sign_l,sign_r,was_rotating,was_braking,positive,range_valid;
    reg [31:0] range_mm;
    reg signed [31:0] error;
    reg [31:0] magnitude;
    reg [16:0] rate;
    reg [25:0] brake_product;
    reg [31:0] numerator;
    reg [15:0] denominator;
    reg start;
    wire div_done,div_busy;
    wire [31:0] quotient;
    wire abort_job=cancel || !enable || (state!=IDLE && was_rotating!=rotating);
    a741_divider divider(.clk(clk),.rst_n(rst_n),.cancel(abort_job),.start(start),
        .numerator(numerator),.denominator(denominator),.busy(div_busy),.done(div_done),.quotient(quotient));
    wire [10:0] abs_l=wl<0 ? -wl:wl;
    wire signed [15:0] wrapped_delta=yaw-heading_origin;
    wire signed [16:0] extended_delta={wrapped_delta[15],wrapped_delta};
    wire [10:0] abs_r=wr<0 ? -wr:wr;
    wire [10:0] pair_peak=abs_l>abs_r ? abs_l:abs_r;
    wire signed [11:0] pair_sum=$signed(wl)+$signed(wr);
    wire signed [16:0] corrected_rate=$signed({gz[15],gz})-$signed({gyro_bias[15],gyro_bias});
    wire [31:0] speed_l_abs=left_speed<0 ? -left_speed:left_speed;
    wire [31:0] speed_r_abs=right_speed<0 ? -right_speed:right_speed;
    wire [31:0] speed_peak=speed_l_abs>speed_r_abs ? speed_l_abs:speed_r_abs;
    wire [31:0] threshold=quotient>3732 ? 32'd4096:quotient+32'd364;
    wire [31:0] turn_magnitude=magnitude>>5;
    wire [8:0] turn_output=turn_magnitude>turn_cap ? turn_cap:
        turn_magnitude<40 ? 9'd40:turn_magnitude[8:0];
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=IDLE;valid<=0;braking<=0;target_l<=0;target_r<=0;
            wl<=0;wr<=0;corr<=0;delta<=0;cap<=0;turn_cap<=0;peak<=0;factor<=0;
            scale_divisor<=1;sign_l<=0;sign_r<=0;was_rotating<=0;was_braking<=0;positive<=0;
            range_valid<=0;range_mm<=0;error<=0;magnitude<=0;rate<=0;brake_product<=0;
            numerator<=0;denominator<=1;start<=0;after_scale<=IDLE;
        end else begin
            valid<=0;start<=0;
            if(abort_job) begin state<=IDLE;braking<=0;end
            else case(state)
                IDLE: if(tick) begin
                    wl<=desired_l;wr<=desired_r;cap<=max_speed;turn_cap<=turn_speed;
                    delta<=heading_positive ? extended_delta:-extended_delta;
                    positive<=heading_hold;was_rotating<=rotating;was_braking<=turn_braking;
                    range_mm<=clearance;range_valid<=tof_valid;
                    error<=turn_target-accumulated_yaw;
                    magnitude<=turn_target>=accumulated_yaw ? turn_target-accumulated_yaw:accumulated_yaw-turn_target;
                    rate<=corrected_rate<0 ? -corrected_rate:corrected_rate;
                    if(rotating) begin
                        numerator<=speed_peak>400 ? 32'd400:speed_peak;
                        denominator<=speed_step==0 ? 16'd1:{10'd0,speed_step};
                        start<=1;state<=BRAKE_WAIT;
                    end else state<=NORM;
                end
                NORM: begin
                    // Signed division by 64 truncates towards zero.
                    if(!positive) corr<=0;
                    else if(delta>1280) corr<=20;
                    else if(delta < -1280) corr<=-20;
                    else corr<=delta<0 ? -((-delta)>>6):delta>>6;
                    if(pair_peak>cap) begin
                        sign_l<=wl<0;sign_r<=wr<0;factor<=cap;scale_divisor<={5'd0,pair_peak};
                        numerator<=abs_l*cap;denominator<={5'd0,pair_peak};start<=1;
                        after_scale<=CORRECT;state<=LEFT_WAIT;
                    end else state<=CORRECT;
                end
                LEFT_WAIT: if(div_done) begin wl<=sign_l ? -$signed(quotient[10:0]):$signed(quotient[10:0]);state<=RIGHT_START;end
                RIGHT_START: begin numerator<=abs_r*factor;denominator<=scale_divisor;start<=1;state<=RIGHT_WAIT;end
                RIGHT_WAIT: if(div_done) begin wr<=sign_r ? -$signed(quotient[10:0]):$signed(quotient[10:0]);state<=after_scale;end
                CORRECT: begin wl<=wl+corr;wr<=wr-corr;state<=RECHECK;end
                RECHECK: if(pair_peak>cap) begin
                    sign_l<=wl<0;sign_r<=wr<0;factor<=cap;scale_divisor<={5'd0,pair_peak};
                    numerator<=abs_l*cap;denominator<={5'd0,pair_peak};start<=1;
                    after_scale<=TOF;state<=LEFT_WAIT;
                end else state<=TOF;
                TOF: begin
                    if(pair_sum>0 && (!range_valid || range_mm<=250)) begin wl<=0;wr<=0;state<=DONE;end
                    else if(pair_sum>0 && range_mm<500) begin
                        sign_l<=wl<0;sign_r<=wr<0;factor<=range_mm-250;scale_divisor<=250;
                        numerator<=abs_l*(range_mm[8:0]-9'd250);denominator<=250;start<=1;
                        after_scale<=DONE;state<=LEFT_WAIT;
                    end else state<=DONE;
                end
                DONE: begin target_l<=wl;target_r<=wr;braking<=0;valid<=1;state<=IDLE;end
                BRAKE_WAIT: if(div_done) begin peak<=quotient[8:0]+9'd8;state<=BRAKE_MUL;end
                BRAKE_MUL: begin brake_product<=rate*peak;state<=BRAKE_DIV;end
                BRAKE_DIV: begin numerator<={6'd0,brake_product};denominator<=18;start<=1;state<=BRAKE_DECIDE;end
                BRAKE_DECIDE: if(div_done) begin
                    if(was_braking || (error>=0 && $unsigned(error)<=threshold) ||
                        (error<0 && $unsigned(-error)<=threshold) ||
                        (turn_target>0 && error<0) || (turn_target<0 && error>0)) begin
                        target_l<=0;target_r<=0;braking<=1;
                    end else begin
                        target_l<=error<0 ? $signed({1'b0,turn_output}):-$signed({1'b0,turn_output});
                        target_r<=error<0 ? -$signed({1'b0,turn_output}):$signed({1'b0,turn_output});
                        braking<=0;
                    end
                    valid<=1;state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
endmodule
`default_nettype wire
