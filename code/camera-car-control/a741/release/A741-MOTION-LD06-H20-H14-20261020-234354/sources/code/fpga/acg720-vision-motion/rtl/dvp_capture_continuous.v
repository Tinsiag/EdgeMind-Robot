`timescale 1ns/1ps
`default_nettype none
// OV5640 RGB565: VSYNC high during frame blanking; high byte first.
module dvp_capture_continuous #(
    parameter WIDTH=800, HEIGHT=480, SKIP_FRAMES=10
)(
    input wire pclk,rst_n,enable,vsync,href, input wire [7:0] data,
    output reg pixel_valid, output reg [15:0] pixel,
    output reg [10:0] pixel_x,pixel_y,
    output reg frame_start,frame_end,frame_good,frame_error
);
    reg prev_vs,prev_href,active,half_byte,bad;
    reg [7:0] first_byte;
    reg [11:0] column,row;
    reg [31:0] pixels,skipped;
    always @(posedge pclk or negedge rst_n)
        if(!rst_n) begin
            prev_vs<=1;prev_href<=0;active<=0;half_byte<=0;bad<=0;first_byte<=0;
            column<=0;row<=0;pixels<=0;skipped<=0;pixel_valid<=0;pixel<=0;
            pixel_x<=0;pixel_y<=0;frame_start<=0;frame_end<=0;frame_good<=0;frame_error<=0;
        end else begin
            prev_vs<=vsync;prev_href<=href;pixel_valid<=0;frame_start<=0;frame_end<=0;
            if(!enable) begin active<=0;half_byte<=0;skipped<=0;prev_vs<=1;prev_href<=0;end
            else if(prev_vs && !vsync) begin
                active<=1;column<=0;row<=0;pixels<=0;half_byte<=0;bad<=href;
                frame_start<=1;frame_good<=0;frame_error<=0;
            end else if(!prev_vs && vsync && active) begin
                active<=0;frame_end<=1;half_byte<=0;
                frame_error<=bad || half_byte || href || prev_href || row!=HEIGHT || column!=0 || pixels!=WIDTH*HEIGHT;
                frame_good<=!bad && !half_byte && !href && !prev_href && row==HEIGHT && column==0 && pixels==WIDTH*HEIGHT && skipped>=SKIP_FRAMES;
                if(skipped<SKIP_FRAMES) skipped<=skipped+1'b1;
            end else if(active && !vsync) begin
                if(prev_href && !href) begin
                    if(half_byte || column!=WIDTH || row>=HEIGHT) bad<=1;
                    column<=0;half_byte<=0;
                    if(row<4095) row<=row+1'b1; else bad<=1;
                end
                if(href) begin
                    if(!half_byte) begin first_byte<=data;half_byte<=1;end
                    else begin
                        half_byte<=0;
                        if(column<WIDTH && row<HEIGHT) begin
                            pixel<={first_byte,data};pixel_x<=column[10:0];pixel_y<=row[10:0];pixel_valid<=1;
                        end else bad<=1;
                        if(column<4095) column<=column+1'b1; else bad<=1;
                        pixels<=pixels+1'b1;
                    end
                end
            end
        end
endmodule
`default_nettype wire
