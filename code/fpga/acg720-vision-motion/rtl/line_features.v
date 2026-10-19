`timescale 1ns/1ps
`default_nettype none
module line_features #(parameter WIDTH=800,HEIGHT=480)(
    input wire clk,rst_n,frame_start,frame_end,frame_good,pixel_valid,
    input wire [15:0] pixel, input wire [10:0] x,y,
    input wire [7:0] threshold,
    input wire [10:0] near_y0,near_y1,far_y0,far_y1,
    output reg result_valid, output reg [1:0] regions_valid,
    output reg [10:0] near_center,far_center, output reg [15:0] frame_id
);
    wire [7:0] r={pixel[15:11],pixel[15:13]};
    wire [7:0] g={pixel[10:5],pixel[10:9]};
    wire [7:0] b={pixel[4:0],pixel[4:2]};
    wire [9:0] luminance={2'b0,r}+{1'b0,g,1'b0}+{2'b0,b};
    wire dark=luminance < {threshold,2'b0};
    reg [31:0] near_sum,far_sum,near_count,far_count;
    reg [31:0] sum_save,count_save;
    reg div_start;reg [31:0] num,den;wire busy,done;wire [31:0] quotient;
    reg [2:0] state;reg [1:0] pending_valid;
    unsigned_divider div(.clk(clk),.rst_n(rst_n),.start(div_start),.numerator(num),.denominator(den),.busy(busy),.done(done),.quotient(quotient));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            near_sum<=0;far_sum<=0;near_count<=0;far_count<=0;sum_save<=0;count_save<=0;
            num<=0;den<=0;div_start<=0;state<=0;pending_valid<=0;regions_valid<=0;
            result_valid<=0;near_center<=WIDTH/2;far_center<=WIDTH/2;frame_id<=0;
        end else begin
            result_valid<=0;div_start<=0;
            if(frame_start) begin near_sum<=0;far_sum<=0;near_count<=0;far_count<=0;end
            if(pixel_valid && dark) begin
                if(y>=near_y0 && y<=near_y1) begin near_sum<=near_sum+x;near_count<=near_count+1'b1;end
                if(y>=far_y0 && y<=far_y1) begin far_sum<=far_sum+x;far_count<=far_count+1'b1;end
            end
            case(state)
                0: if(frame_end) begin
                    pending_valid[0]<=frame_good && near_count>=16 && near_count<=WIDTH*(near_y1-near_y0+1)/2;
                    pending_valid[1]<=frame_good && far_count>=16 && far_count<=WIDTH*(far_y1-far_y0+1)/2;
                    num<=near_sum;den<=near_count;sum_save<=far_sum;count_save<=far_count;
                    div_start<=1;state<=1;
                end
                1: if(done) begin near_center<=quotient[10:0];num<=sum_save;den<=count_save;state<=2;end
                2: begin div_start<=1;state<=3;end
                3: if(done) begin
                    far_center<=quotient[10:0];regions_valid<=pending_valid;
                    result_valid<=1;frame_id<=frame_id+1'b1;state<=0;
                end
                default: state<=0;
            endcase
        end
endmodule
`default_nettype wire
