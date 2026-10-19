`timescale 1ns/1ps
`default_nettype none
module capture_tokens(
    input wire clk,rst_n,frame_start,frame_end,frame_good,pixel_valid,
    input wire [15:0] pixel,input wire fifo_full,
    output reg fifo_write,output reg [17:0] fifo_data,output reg overflow
);
    reg active,bad,end_pending,end_good;
    always @* begin
        fifo_write=0;fifo_data=0;
        if(!fifo_full) begin
            if(end_pending) begin fifo_write=1;fifo_data={end_good?2'b10:2'b11,16'd0};end
            else if(frame_start) begin fifo_write=1;fifo_data={2'b01,16'd0};end
            else if(pixel_valid && active && !bad) begin fifo_write=1;fifo_data={2'b00,pixel};end
        end
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin active<=0;bad<=0;end_pending<=0;end_good<=0;overflow<=0;end
        else begin
            if(end_pending && !fifo_full) begin
                end_pending<=0;
            end else if(frame_start) begin
                bad<=0;
                if(!fifo_full && !end_pending) begin active<=1;end
                else begin active<=0;overflow<=1;end
            end else if(frame_end && active) begin
                active<=0;end_pending<=1;end_good<=frame_good && !bad;
            end else if(pixel_valid && active && !bad) begin
                if(fifo_full) begin bad<=1;overflow<=1;end
            end
        end
endmodule
`default_nettype wire
