`timescale 1ns/1ps
`default_nettype none
// All targets and feedback use vehicle-forward-positive coordinates.
module motion_core #(parameter CLK_HZ=50000000,PWM_HZ=1000,RIGHT_INVERT=1)(
    input wire clk,rst_n,enable,clear_fault,
    input wire left_a,left_b,right_a,right_b,
    input wire signed [31:0] left_target,right_target,
    input wire [15:0] output_limit,ramp_limit,
    input wire [31:0] cpr_l,cpr_r,diam_l,diam_r,
    output wire left_in1,left_in2,right_in1,right_in2,
    output wire signed [31:0] left_count,right_count,left_speed,right_speed,
    output wire [15:0] left_pwm,right_pwm,
    output reg [15:0] faults,
    output wire [31:0] left_invalid_count,right_invalid_count,
    output wire ms_tick,control_tick
);
    reg [31:0] divider;reg [3:0] sample_div;
    assign ms_tick=divider==CLK_HZ/1000-1;
    assign control_tick=ms_tick && sample_div==9;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin divider<=0;sample_div<=0;end
        else if(ms_tick) begin divider<=0;sample_div<=sample_div==9 ? 4'd0:sample_div+4'd1;end
        else divider<=divider+1'b1;
    wire signed [1:0] ls,rs;wire li,ri,lto,rto;
    wire signed [31:0] ld,rd;
    quadrature_decoder ql(.clk(clk),.rstn(rst_n),.a(left_a),.b(left_b),.invert(1'b0),.step(ls),.invalid(li));
    quadrature_decoder qr(.clk(clk),.rstn(rst_n),.a(right_a),.b(right_b),.invert(1'b1),.step(rs),.invalid(ri));
    wire run=enable && faults==0;
    encoder_counter el(.clk(clk),.rstn(rst_n),.step(ls),.invalid_step(li),.sample_tick(control_tick),.monitor_enable(run && left_target!=0),.count(left_count),.delta(ld),.invalid_count(left_invalid_count),.feedback_timeout(lto));
    encoder_counter er(.clk(clk),.rstn(rst_n),.step(rs),.invalid_step(ri),.sample_tick(control_tick),.monitor_enable(run && right_target!=0),.count(right_count),.delta(rd),.invalid_count(right_invalid_count),.feedback_timeout(rto));
    // Encoder delta is registered on control_tick; start conversion next cycle,
    // then start PI only after both current-window conversions are ready.
    reg convert;wire lv,rv;wire signed [31:0] lp,rp;
    always @(posedge clk or negedge rst_n) if(!rst_n) convert<=0;else convert<=control_tick;
    wheel_speed_estimator sl(.clk(clk),.rstn(rst_n),.sample_tick(convert),.delta_count(ld),.cpr(cpr_l),.diameter_mm(diam_l),.speed_mm_s(left_speed),.valid(lv));
    wheel_speed_estimator sr(.clk(clk),.rstn(rst_n),.sample_tick(convert),.delta_count(rd),.cpr(cpr_r),.diameter_mm(diam_r),.speed_mm_s(right_speed),.valid(rv));
    wire signed [31:0] applied_l,applied_r;
    wire drive_enable=run && !lto && !rto;
    wheel_pi_controller pil(.clk(clk),.rstn(rst_n),.update(lv && rv),.enable(drive_enable),.target_speed(left_target),.measured_speed(left_speed),.output_limit(output_limit>512?16'd512:output_limit),.ramp_limit(ramp_limit),.command(lp),.applied_target(applied_l));
    wheel_pi_controller pir(.clk(clk),.rstn(rst_n),.update(lv && rv),.enable(drive_enable),.target_speed(right_target),.measured_speed(right_speed),.output_limit(output_limit>512?16'd512:output_limit),.ramp_limit(ramp_limit),.command(rp),.applied_target(applied_r));
    motor_pwm_safe #(.CLK_HZ(CLK_HZ),.PWM_HZ(PWM_HZ),.INVERT(0)) dl(.clk(clk),.rst_n(rst_n),.enable(drive_enable),.command(lp),.in1(left_in1),.in2(left_in2),.pwm_abs(left_pwm));
    motor_pwm_safe #(.CLK_HZ(CLK_HZ),.PWM_HZ(PWM_HZ),.INVERT(RIGHT_INVERT)) dr(.clk(clk),.rst_n(rst_n),.enable(drive_enable),.command(rp),.in1(right_in1),.in2(right_in2),.pwm_abs(right_pwm));
    reg [4:0] reverse_l,reverse_r;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin faults<=0;reverse_l<=0;reverse_r<=0;end
        else begin
            if(clear_fault && !enable) begin faults<=0;reverse_l<=0;reverse_r<=0;end
            else begin
                if(run && (lto || rto)) faults[2]<=1;
                if(lv && rv) begin
                    if(run && ((left_target>0 && left_speed < -20)||(left_target<0 && left_speed>20))) begin
                        if(reverse_l<19) reverse_l<=reverse_l+1'b1;else faults[3]<=1;
                    end else reverse_l<=0;
                    if(run && ((right_target>0 && right_speed < -20)||(right_target<0 && right_speed>20))) begin
                        if(reverse_r<19) reverse_r<=reverse_r+1'b1;else faults[3]<=1;
                    end else reverse_r<=0;
                end
            end
        end
endmodule
`default_nettype wire
