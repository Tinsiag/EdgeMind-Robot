`timescale 1ns/1ps
`default_nettype none
module video_pixels(
    input wire clk,rst_n,de,frame_blank,flush,
    input wire [127:0] fifo_data,input wire fifo_empty,output wire fifo_pop,
    output reg flush_done,output wire [15:0] pixel,output wire pixel_valid,
    output reg underrun
);
    reg [127:0] shift;reg [3:0] remaining;reg draining,failed;
    // Prefetch during blanking as soon as the UI has completed a flush.
    assign fifo_pop=draining ? !fifo_empty:(remaining==0 || (de && remaining==1)) && !fifo_empty && !failed && !frame_blank && !flush;
    assign pixel=shift[15:0];
    assign pixel_valid=de && remaining!=0 && !failed && !draining;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin shift<=0;remaining<=0;draining<=0;failed<=1;flush_done<=0;underrun<=0;end
        else begin
            flush_done<=0;
            if(frame_blank) begin failed<=1;remaining<=0;end
            if(flush) begin draining<=1;remaining<=0;failed<=1;end
            else if(draining) begin
                if(fifo_empty) begin draining<=0;failed<=0;flush_done<=1;end
            end else if(!frame_blank) begin
                if(fifo_pop) begin shift<=fifo_data;remaining<=8;end
                else if(de && !failed) begin
                    if(remaining==0) begin underrun<=1;failed<=1;end
                    else begin shift<={16'd0,shift[127:16]};remaining<=remaining-1'b1;end
                end
            end
        end
endmodule
`default_nettype wire
