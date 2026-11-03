`timescale 1ns/1ps
`default_nettype none
// ACG720 chapter13: MSB-first {dp, active-low segments, active-high digit}.
// One clock domain; outputs change only on a divided clock enable.
module a745_mode_display #(parameter DIV=250)(
 input wire clk,rst_n,input wire [1:0] mode,
 output reg dio,rclk,sclk
);
 reg [15:0] timer,shift;reg [5:0] phase;
 reg [6:0] segments;
 always @* case(mode)
  1:segments=7'b1111001;2:segments=7'b0100100;3:segments=7'b0110000;
  default:segments=7'b0111111;
 endcase
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin timer<=0;phase<=0;shift<=16'hff00;dio<=0;rclk<=0;sclk<=0;end
  else if(timer==DIV-1) begin
   timer<=0;
   if(phase==0) begin shift<={1'b1,segments,8'h01};rclk<=0;sclk<=0;phase<=1;end
   else if(phase<=32) begin
    if(phase[0]) begin sclk<=0;dio<=shift[15];end
    else begin sclk<=1;shift<={shift[14:0],1'b0};end
    phase<=phase+1'b1;
   end else if(phase==33) begin sclk<=0;rclk<=1;phase<=34;end
   else begin rclk<=0;phase<=0;end
  end else timer<=timer+1'b1;
endmodule
`default_nettype wire
