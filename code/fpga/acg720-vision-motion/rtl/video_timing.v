`timescale 1ns/1ps
`default_nettype none
// 800x480 @ 33 MHz; board wrapper supplies pixel33 and TMDS165.
module video_timing #(parameter WIDTH=800,HEIGHT=480,HFP=40,HS=128,HBP=88,VFP=13,VS=2,VBP=31)(
    input wire clk,rst_n,output wire de,hsync,vsync,frame_blank,
    output wire [10:0] x,y
);
    localparam HT=WIDTH+HFP+HS+HBP,VT=HEIGHT+VFP+VS+VBP;
    reg [10:0] h,v;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin h<=0;v<=0;end
        else if(h==HT-1) begin h<=0;v<=v==VT-1 ? 11'd0:v+11'd1;end
        else h<=h+11'd1;
    assign de=h<WIDTH && v<HEIGHT;
    assign x=h;assign y=v;
    assign hsync=!(h>=WIDTH+HFP && h<WIDTH+HFP+HS);
    assign vsync=!(v>=HEIGHT+VFP && v<HEIGHT+VFP+VS);
    assign frame_blank=h==0 && v==HEIGHT;
endmodule
`default_nettype wire
