`timescale 1ns/1ps
`default_nettype none
// Build an immutable planning snapshot, with a conservative square footprint.
// A square circumscribing the rotation disk is deliberately more restrictive.
module a741_inflate(
    input wire clk,rst_n,start,cancel,input wire [4:0] radius_cells,
    output reg busy,ready,output reg raw_read,output reg [13:0] raw_address,
    input wire raw_done,input wire [1:0] raw_value,
    input wire query,input wire [13:0] query_address,output reg query_done,output reg [1:0] query_value
);
    reg free_cells[0:16383],blocked[0:16383];
    reg free_q,blocked_q,query_pending;
    reg [3:0] state;reg [13:0] index;reg signed [6:0] dx,dy,radius;
    wire signed [8:0] tx=$signed({1'b0,index[6:0]})+dx;
    wire signed [8:0] ty=$signed({1'b0,index[13:7]})+dy;
    always @(posedge clk) begin free_q<=free_cells[query_address];blocked_q<=blocked[query_address];end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin busy<=0;ready<=0;raw_read<=0;raw_address<=0;query_done<=0;query_value<=0;state<=0;index<=0;dx<=0;dy<=0;radius<=0;query_pending<=0;end
        else begin
            raw_read<=0;query_done<=0;
            query_pending<=query && ready;
            if(query_pending && ready) begin query_done<=1;query_value<=free_q && !blocked_q ? 2'b01:2'b10;end
            if(cancel) begin state<=0;busy<=0;ready<=0;end
            else case(state)
                0:if(start) begin state<=1;busy<=1;ready<=0;index<=0;radius<={2'b0,radius_cells};end
                1:begin blocked[index]<=0;if(index==16383) begin index<=0;state<=2;end else index<=index+1'b1;end
                2:begin raw_read<=1;raw_address<=index;state<=3;end
                3:if(raw_done) begin
                    free_cells[index]<=raw_value==2'b01;
                    if(raw_value!=2'b01) begin dx<=-radius;dy<=-radius;state<=4;end
                    else state<=5;
                end
                4:begin
                    if(tx>=0 && tx<128 && ty>=0 && ty<128) blocked[{ty[6:0],tx[6:0]}]<=1;
                    if(dx==radius) begin dx<=-radius;if(dy==radius) state<=5;else dy<=dy+1'b1;end
                    else dx<=dx+1'b1;
                end
                5:if(index==16383) begin busy<=0;ready<=1;state<=0;end
                    else begin index<=index+1'b1;state<=2;end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
