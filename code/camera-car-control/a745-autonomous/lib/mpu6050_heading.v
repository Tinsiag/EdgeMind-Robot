`timescale 1ns/1ps
`default_nettype none
// Planar Z-axis relative yaw only; accelerometers cannot observe yaw drift.
// The accumulator preserves sub-Q15-turn fractions at a 100 Hz sample rate.
module mpu6050_heading(
    input wire clk,rst_n,sample_update,sample_valid,
    input wire signed [15:0] raw_gz,ax,ay,az,
    input wire [31:0] sample_time,
    input wire calibrated,input wire signed [15:0] gyro_bias,
    output reg signed [15:0] yaw,gz,
    output reg angle_update,gyro_update,
    output wire valid,stationary
);
    localparam IDLE=0,NORMALIZE=1,CORRECT=2,MULTIPLY=3,PREPARE=4,INTEGRATE=5,COMMIT=6,SIGN=7;
    reg [2:0] state;
    reg have_previous,was_calibrated,gap_error;
    reg [31:0] previous_time;
    reg signed [47:0] phase;
    reg raw_negative,increment_negative,pending_integrate,pending_uncalibrated;
    reg [4:0] pending_dt;
    reg signed [15:0] pending_bias,converted;
    reg signed [16:0] corrected;
    reg signed [21:0] product;
    reg [37:0] work;
    reg [10:0] divisor,remainder;
    reg [5:0] count;
    wire [15:0] raw_magnitude=raw_gz[15] ? (~raw_gz+16'd1):raw_gz;
    wire [31:0] interval=sample_time-previous_time;
    wire [11:0] trial={remainder,work[37]};
    wire subtract=trial>={1'b0,divisor};
    wire [11:0] reduced=trial-{1'b0,divisor};
    wire [37:0] next_work={work[36:0],subtract};
    wire signed [47:0] magnitude={10'd0,work};
    reg signed [47:0] increment;
    wire signed [47:0] next_phase=phase+increment;
    assign stationary=ax> -4096 && ax<4096 && ay> -4096 && ay<4096 &&
        ((az>13926 && az<18842)||(az< -13926 && az> -18842));
    assign valid=sample_valid && have_previous && !gap_error;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin yaw<=0;gz<=0;angle_update<=0;gyro_update<=0;have_previous<=0;
            was_calibrated<=0;previous_time<=0;phase<=0;gap_error<=0;state<=IDLE;
            raw_negative<=0;increment_negative<=0;pending_integrate<=0;pending_uncalibrated<=0;
            pending_dt<=0;pending_bias<=0;converted<=0;corrected<=0;product<=0;
            work<=0;divisor<=1;remainder<=0;count<=0;increment<=0;end
        else begin
            angle_update<=0;gyro_update<=0;was_calibrated<=calibrated;
            if(!sample_valid) begin
                have_previous<=0;phase<=0;yaw<=0;gap_error<=0;state<=IDLE;
            end else if(calibrated!=was_calibrated) begin
                // Do not commit calculations that belong to the previous calibration.
                phase<=0;yaw<=0;state<=IDLE;
            end else if(sample_update) begin
                if(state!=IDLE) begin
                    // A 100 Hz source cannot overrun this sub-2us pipeline. Fail closed if it does.
                    have_previous<=0;phase<=0;yaw<=0;gap_error<=1;state<=IDLE;
                end else begin
                    previous_time<=sample_time;have_previous<=1;
                    gap_error<=have_previous && (interval==0 || interval>30);
                    pending_integrate<=have_previous && interval>0 && interval<=30 && calibrated;
                    pending_uncalibrated<=!calibrated;pending_dt<=interval[4:0];pending_bias<=gyro_bias;
                    raw_negative<=raw_gz[15];work<={12'd0,raw_magnitude,10'd0};
                    divisor<=11'd1025;remainder<=0;count<=0;state<=NORMALIZE;
                end
            end else case(state)
                NORMALIZE,INTEGRATE: begin
                    // Shared restoring divider: one quotient bit per cycle, signed via magnitudes.
                    remainder<=subtract ? reduced[10:0]:trial[10:0];work<=next_work;
                    if(count==37) begin
                        if(state==NORMALIZE) begin
                            converted<=raw_negative ? -$signed(next_work[15:0]):$signed(next_work[15:0]);
                            state<=CORRECT;
                        end else state<=SIGN;
                    end else count<=count+1'b1;
                end
                CORRECT: begin
                    if(pending_integrate) begin
                        corrected<=$signed({converted[15],converted})-$signed({pending_bias[15],pending_bias});
                        state<=MULTIPLY;
                    end else state<=COMMIT;
                end
                MULTIPLY: begin
                    product<=corrected*$signed({1'b0,pending_dt});state<=PREPARE;
                end
                PREPARE: begin
                    // |corrected|<=65503, dt<=30: 22 product bits plus 16 fractional bits.
                    work<=product[21] ? {(-product),16'd0}:{product,16'd0};
                    increment_negative<=product[21];divisor<=11'd90;remainder<=0;count<=0;
                    state<=INTEGRATE;
                end
                SIGN: begin
                    // Separate signed quotient negation from phase addition.
                    increment<=increment_negative ? -magnitude:magnitude;
                    state<=COMMIT;
                end
                COMMIT: begin
                    gz<=converted;gyro_update<=1;
                    if(pending_integrate) begin
                        phase<=next_phase;yaw<=next_phase[31:16];angle_update<=1;
                    end else if(pending_uncalibrated) begin phase<=0;yaw<=0;angle_update<=1;end
                    state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
endmodule
`default_nettype wire
