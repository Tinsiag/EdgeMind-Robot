`timescale 1ns/1ps
`default_nettype none
module unsigned_divider(
    input wire clk,rst_n,start, input wire [31:0] numerator,denominator,
    output reg busy,done, output reg [31:0] quotient
);
    reg [31:0] dividend,divisor,q;
    reg [32:0] rem_q;
    reg [5:0] bits_left;
    wire [32:0] shifted={rem_q[31:0],dividend[31]};
    wire ge=shifted>={1'b0,divisor};
    wire [31:0] q_next={q[30:0],ge};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin busy<=0;done<=0;quotient<=0;dividend<=0;divisor<=0;q<=0;rem_q<=0;bits_left<=0;end
        else begin
            done<=0;
            if(start && !busy) begin
                if(denominator==0) begin quotient<=0;done<=1;end
                else begin dividend<=numerator;divisor<=denominator;q<=0;rem_q<=0;bits_left<=32;busy<=1;end
            end else if(busy) begin
                rem_q<=ge ? shifted-{1'b0,divisor}:shifted;
                dividend<={dividend[30:0],1'b0};q<=q_next;bits_left<=bits_left-1'b1;
                if(bits_left==1) begin quotient<=q_next;busy<=0;done<=1;end
            end
        end
endmodule
`default_nettype wire
