`timescale 1ns/1ps
`default_nettype none
// Bresenham ray rasterizer. Emits free cells up to the endpoint and marks the
// endpoint occupied. One cell update is produced per clock.
module a741_ray_mapper(
    input wire clk,rst_n,start,cancel,
    input wire [6:0] origin_x,origin_y,endpoint_x,endpoint_y,
    output reg busy,update_valid,output reg [6:0] update_x,update_y,
    output reg [1:0] update_value,output reg done,invalid
);
    reg [6:0] x1,y1;
    reg signed [9:0] x,y,dx,dy,err;
    wire signed [10:0] e2=$signed(err)*2;
    wire advance_x=e2> -$signed(dy);
    wire advance_y=e2<$signed(dx);
    reg signed [1:0] sx,sy;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            x1<=0;y1<=0;x<=0;y<=0;dx<=0;dy<=0;err<=0;sx<=0;sy<=0;
            busy<=0;update_valid<=0;update_x<=0;update_y<=0;update_value<=0;done<=0;invalid<=0;
        end else begin
            update_valid<=0;done<=0;invalid<=0;
            if(cancel) busy<=0;
            else if(start && !busy) begin
                if(origin_x>=128 || origin_y>=128 || endpoint_x>=128 || endpoint_y>=128) invalid<=1;
                else begin
                    x<={2'b0,origin_x};y<={2'b0,origin_y};x1<=endpoint_x;y1<=endpoint_y;
                    dx<=origin_x>endpoint_x ? origin_x-endpoint_x:endpoint_x-origin_x;
                    dy<=origin_y>endpoint_y ? origin_y-endpoint_y:endpoint_y-origin_y;
                    sx<=origin_x<endpoint_x ? 1:-1;sy<=origin_y<endpoint_y ? 1:-1;
                    err<=(origin_x>endpoint_x ? origin_x-endpoint_x:endpoint_x-origin_x)-
                         (origin_y>endpoint_y ? origin_y-endpoint_y:endpoint_y-origin_y);
                    busy<=1;
                end
            end else if(busy) begin
                update_valid<=1;update_x<=x[6:0];update_y<=y[6:0];
                if(x==x1 && y==y1) begin
                    update_value<=2'b10;busy<=0;done<=1;
                end else begin
                    update_value<=2'b01;
                    err<=err-(advance_x ? dy:10'sd0)+(advance_y ? dx:10'sd0);
                    if(advance_x) x<=x+sx;
                    if(advance_y) y<=y+sy;
                end
            end
        end
endmodule
`default_nettype wire
