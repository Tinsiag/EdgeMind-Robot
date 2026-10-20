`timescale 1ns/1ps
`default_nettype none
// Unsigned restoring division: one quotient bit per clock, no combinational /.
module a741_divider(
    input wire clk,rst_n,cancel,start,
    input wire [31:0] numerator,
    input wire [15:0] denominator,
    output reg busy,done,
    output reg [31:0] quotient
);
    reg [31:0] work;
    reg [15:0] divisor,remainder;
    reg [5:0] count;
    wire [16:0] trial={remainder,work[31]};
    wire subtract=trial>={1'b0,divisor};
    wire [16:0] reduced=trial-{1'b0,divisor};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin busy<=0;done<=0;quotient<=0;work<=0;divisor<=1;remainder<=0;count<=0;end
        else begin
            done<=0;
            if(cancel) busy<=0;
            else if(start && !busy) begin
                work<=numerator;divisor<=denominator==0 ? 16'd1:denominator;
                remainder<=0;count<=0;busy<=1;
            end else if(busy) begin
                remainder<=subtract ? reduced[15:0]:trial[15:0];
                work<={work[30:0],subtract};
                if(count==31) begin quotient<={work[30:0],subtract};busy<=0;done<=1;end
                else count<=count+1'b1;
            end
        end
endmodule
`default_nettype wire
