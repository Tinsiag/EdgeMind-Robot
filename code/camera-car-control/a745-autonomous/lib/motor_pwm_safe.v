`timescale 1ns/1ps
`default_nettype none
module motor_pwm_safe #(parameter CLK_HZ=50000000,PWM_HZ=1000,INVERT=0)(
    input wire clk,rst_n,enable, input wire signed [31:0] command,
    output wire in1,in2, output wire [15:0] pwm_abs
);
    localparam PERIOD=CLK_HZ/PWM_HZ;
    reg [31:0] phase,duty_q;
    reg direction_q,dead;
    reg [15:0] magnitude_q;
    wire desired=(command<0) ^ (INVERT!=0);
    wire [31:0] mag=(command<0) ? -command:command;
    wire [31:0] limited=mag>512 ? 512:mag;
    // Output gate is combinational so a confirmed STOP does not wait for PWM.
    assign in1=enable && rst_n && command!=0 && !dead && !direction_q && phase<duty_q;
    assign in2=enable && rst_n && command!=0 && !dead && direction_q && phase<duty_q;
    assign pwm_abs=enable && !dead && command!=0 ? magnitude_q:16'd0;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin phase<=0;duty_q<=0;direction_q<=0;dead<=1;magnitude_q<=0;end
        else begin
            if(phase==PERIOD-1) begin
                phase<=0;
                if(!enable || command==0) begin duty_q<=0;magnitude_q<=0;dead<=1;end
                else if(desired!=direction_q) begin direction_q<=desired;duty_q<=0;magnitude_q<=0;dead<=1;end
                else begin duty_q<=(limited*PERIOD)>>10;magnitude_q<=limited[15:0];dead<=0;end
            end else phase<=phase+1'b1;
            if(!enable || command==0) begin duty_q<=0;magnitude_q<=0;dead<=1;end
        end
endmodule
`default_nettype wire
