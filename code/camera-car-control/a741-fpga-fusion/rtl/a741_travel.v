`timescale 1ns/1ps
`default_nettype none
// Exact encoder interval displacement in Q16 mm, without rounded wheel speeds.
module a741_travel(
    input wire clk,rst_n,start,input wire signed [31:0] delta,
    input wire [31:0] cpr,diameter_um,
    output reg done,valid,output reg signed [31:0] distance_q16
);
    reg [2:0] state;reg negative;reg [6:0] count;
    reg [31:0] magnitude_q;reg [17:0] diameter_q;
    reg [63:0] product;reg [79:0] dividend,quotient;
    reg [34:0] divisor,remainder;
    wire [31:0] magnitude=delta<0 ? -delta:delta;
    wire [35:0] trial={remainder,dividend[79]};
    wire subtract=trial>={1'b0,divisor};
    wire [35:0] reduced=trial-{1'b0,divisor};
    wire [79:0] next_q={quotient[78:0],subtract};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=0;negative<=0;count<=0;product<=0;dividend<=0;quotient<=0;divisor<=1;remainder<=0;
            done<=0;valid<=0;distance_q16<=0;magnitude_q<=0;diameter_q<=0;
        end else begin
            done<=0;
            case(state)
                0:if(start) begin
                    valid<=0;distance_q16<=0;
                    if(cpr<100 || cpr>20000 || diameter_um<10000 || diameter_um>200000) done<=1;
                    else begin
                        magnitude_q<=magnitude;diameter_q<=diameter_um[17:0];divisor<=35'(cpr)*35'd1000000;
                        negative<=delta<0;quotient<=0;remainder<=0;state<=4;
                    end
                end
                1:begin product<=product*64'd3142;state<=2;end
                2:begin dividend<={product,16'd0};count<=80;state<=3;end
                3:begin
                    dividend<={dividend[78:0],1'b0};quotient<=next_q;
                    remainder<=subtract ? reduced[34:0]:trial[34:0];count<=count-1'b1;
                    if(count==1) begin
                        done<=1;valid<=next_q<=80'h7fffffff;state<=0;
                        distance_q16<=next_q>80'h7fffffff ? 0:negative ? -$signed(next_q[31:0]):$signed(next_q[31:0]);
                    end
                end
                4:begin product<=64'(magnitude_q)*diameter_q;state<=1;end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
