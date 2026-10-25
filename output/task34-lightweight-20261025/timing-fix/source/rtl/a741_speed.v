`timescale 1ns/1ps
`default_nettype none
// 64-cycle restoring divide; diameter uses micrometres throughout A741.
module a741_speed(
    input wire clk,rst_n,tick,input wire signed [31:0] delta,
    input wire [31:0] cpr,diameter_um,
    output reg signed [31:0] speed
);
    reg busy,negative;reg [1:0] multiply_pending;reg [6:0] count;
    reg [63:0] dividend,quotient;
    reg [49:0] product;
    reg [31:0] magnitude_q;reg [17:0] diameter_q;
    reg [27:0] divisor,rem_q;
    wire [28:0] shifted={rem_q,dividend[63]};
    // CPR <= 20000 makes cpr*10000 fit 28 bits. One subtraction
    // supplies both the restoring remainder and the comparison borrow.
    wire [29:0] difference={1'b0,shifted}-{2'd0,divisor};
    wire ge=!difference[29];
    wire [63:0] qnext={quotient[62:0],ge};
    wire [31:0] magnitude=delta<0 ? -delta:delta;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin busy<=0;negative<=0;multiply_pending<=0;count<=0;dividend<=0;divisor<=0;quotient<=0;rem_q<=0;speed<=0;product<=0;magnitude_q<=0;diameter_q<=0;end
        else if(tick && !busy && !multiply_pending) begin
            if(cpr<100 || cpr>20000 || diameter_um<10000 || diameter_um>200000) speed<=0;
            else begin
                // Capture magnitude before the DSP input. Diameter is already
                // validated <=200000, so 18 bits and a 50-bit product suffice.
                magnitude_q<=magnitude;diameter_q<=diameter_um[17:0];
                divisor<=cpr[14:0]*28'd10000;
                quotient<=0;rem_q<=0;count<=64;multiply_pending<=1;negative<=delta<0;
            end
        end else if(multiply_pending==1) begin
            product<=50'(magnitude_q)*diameter_q;multiply_pending<=2;
        end else if(multiply_pending==2) begin
            dividend<=product*64'd3142;multiply_pending<=0;busy<=1;
        end else if(busy) begin
            dividend<={dividend[62:0],1'b0};quotient<=qnext;
            rem_q<=ge ? difference[27:0]:shifted[27:0];count<=count-1'b1;
            if(count==1) begin
                busy<=0;
                if(qnext>64'h7fffffff) speed<=negative ? -32'sh7fffffff:32'sh7fffffff;
                else speed<=negative ? -$signed(qnext[31:0]):$signed(qnext[31:0]);
            end
        end
endmodule
`default_nettype wire
