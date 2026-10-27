`timescale 1ns/1ps
`default_nettype none
// Atomic bounded raw wheel targets. No turn, heading or distance controller.
module a741_targets(
    input wire clk,rst_n,enable,tick,cancel,
    input wire signed [10:0] desired_l,desired_r,
    input wire [8:0] max_speed,
    input wire tof_valid,input wire [31:0] clearance,
    output reg valid,
    output reg signed [31:0] target_l,target_r
);
    localparam IDLE=0,NORM=1,LEFT_WAIT=2,RIGHT_START=3,RIGHT_WAIT=4,TOF=5,DONE=6;
    reg [2:0] state,after_scale;
    reg signed [10:0] wl,wr;
    reg [8:0] cap,factor;
    reg [15:0] scale_divisor;
    reg sign_l,sign_r,range_valid;
    reg [31:0] range_mm,numerator;
    reg [15:0] denominator;
    reg start;
    wire div_done;
    wire [31:0] quotient;
    wire abort_job=cancel || !enable;
    a741_divider divider(.clk(clk),.rst_n(rst_n),.cancel(abort_job),.start(start),
        .numerator(numerator),.denominator(denominator),.busy(),.done(div_done),.quotient(quotient));
    wire [10:0] abs_l=wl<0 ? -wl:wl;
    wire [10:0] abs_r=wr<0 ? -wr:wr;
    wire [10:0] pair_peak=abs_l>abs_r ? abs_l:abs_r;
    wire signed [11:0] pair_sum=$signed(wl)+$signed(wr);
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=IDLE;valid<=0;target_l<=0;target_r<=0;
            wl<=0;wr<=0;cap<=0;factor<=0;scale_divisor<=1;
            sign_l<=0;sign_r<=0;range_valid<=0;range_mm<=0;
            numerator<=0;denominator<=1;start<=0;after_scale<=IDLE;
        end else begin
            valid<=0;start<=0;
            if(abort_job) state<=IDLE;
            else case(state)
                IDLE: if(tick) begin
                    wl<=desired_l;wr<=desired_r;cap<=max_speed;
                    range_mm<=clearance;range_valid<=tof_valid;state<=NORM;
                end
                NORM: if(pair_peak>cap) begin
                    sign_l<=wl<0;sign_r<=wr<0;factor<=cap;scale_divisor<={5'd0,pair_peak};
                    numerator<=abs_l*cap;denominator<={5'd0,pair_peak};start<=1;
                    after_scale<=TOF;state<=LEFT_WAIT;
                end else state<=TOF;
                LEFT_WAIT: if(div_done) begin wl<=sign_l ? -$signed(quotient[10:0]):$signed(quotient[10:0]);state<=RIGHT_START;end
                RIGHT_START: begin numerator<=abs_r*factor;denominator<=scale_divisor;start<=1;state<=RIGHT_WAIT;end
                RIGHT_WAIT: if(div_done) begin wr<=sign_r ? -$signed(quotient[10:0]):$signed(quotient[10:0]);state<=after_scale;end
                // Legacy diagnostic profile only; current LD06 profile ties this inactive.
                TOF: begin
                    if(pair_sum>0 && (!range_valid || range_mm<=250)) begin wl<=0;wr<=0;state<=DONE;end
                    else if(pair_sum>0 && range_mm<500) begin
                        sign_l<=wl<0;sign_r<=wr<0;factor<=range_mm-250;scale_divisor<=250;
                        numerator<=abs_l*(range_mm[8:0]-9'd250);denominator<=250;start<=1;
                        after_scale<=DONE;state<=LEFT_WAIT;
                    end else state<=DONE;
                end
                DONE: begin target_l<=wl;target_r<=wr;valid<=1;state<=IDLE;end
                default:state<=IDLE;
            endcase
        end
endmodule
`default_nettype wire
