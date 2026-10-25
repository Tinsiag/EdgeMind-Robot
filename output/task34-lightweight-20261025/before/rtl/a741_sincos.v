`timescale 1ns/1ps
`default_nettype none
module a741_sincos(
    input wire clk,rst_n,start,input wire [15:0] angle,
    output reg busy,done,output reg signed [17:0] cosine,sine
);
    reg signed [31:0] x,y,z;
    reg negative;reg [4:0] index;
    reg signed [31:0] a;
    wire signed [31:0] nx=z>=0 ? x-(y>>>index):x+(y>>>index);
    wire signed [31:0] ny=z>=0 ? y+(x>>>index):y-(x>>>index);
    always @* case(index)
        0:a=8192;1:a=4836;2:a=2555;3:a=1297;4:a=651;5:a=326;
        6:a=163;7:a=81;8:a=41;9:a=20;10:a=10;11:a=5;12:a=3;13:a=1;default:a=1;
    endcase
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin busy<=0;done<=0;cosine<=0;sine<=0;x<=0;y<=0;z<=0;negative<=0;index<=0;end
        else begin
            done<=0;
            if(start && !busy) begin
                if($signed(angle)>16384) begin z<=$signed(angle)-32768;negative<=1;end
                else if($signed(angle)< -16384) begin z<=$signed(angle)+32768;negative<=1;end
                else begin z<=$signed(angle);negative<=0;end
                x<=19898;y<=0;index<=0;busy<=1;
            end else if(busy) begin
                x<=nx;y<=ny;z<=z>=0 ? z-a:z+a;
                if(index==14) begin
                    cosine<=negative ? -nx:nx;sine<=negative ? -ny:ny;done<=1;busy<=0;
                end else index<=index+1'b1;
            end
        end
endmodule
`default_nettype wire
