`timescale 1ns/1ps
`default_nettype none
// A burst FIFO decouples the twelve LD06 points from the iterative projector.
// Endpoint/origin coordinates are signed millimetres in the map frame.
module a741_lidar_project(
    input wire clk,rst_n,valid,point_valid,input wire [15:0] angle_cdeg,distance_mm,
    input wire [7:0] confidence,input wire signed [15:0] heading,
    input wire signed [31:0] pose_x,pose_y,
    input wire signed [15:0] offset_x,offset_y,input wire [15:0] zero_cdeg,input wire clockwise,
    output reg point_done,scan_end,overflow,
    output reg signed [31:0] endpoint_x,endpoint_y,origin_x,origin_y,
    output reg [15:0] body_angle_cdeg,range_mm
);
    reg [39:0] fifo[0:63];reg [5:0] wr,rd;reg [6:0] count;
    reg [3:0] state;reg launch;reg [15:0] trig_angle,angle,range_q,previous_angle;
    reg have_previous;reg signed [31:0] px,py,ox,oy;
    reg signed [15:0] h,ex,ey;wire busy,done;wire signed [17:0] c,s;
    reg signed [47:0] mx,my;
    reg [31:0] normalized;
    reg convert_start;wire convert_busy,convert_done;wire [31:0] angle_raw;
    a741_divider angle_converter(.clk(clk),.rst_n(rst_n),.cancel(!valid),.start(convert_start),
        .numerator({normalized[15:0],16'd0}),.denominator(16'd36000),.busy(convert_busy),.done(convert_done),.quotient(angle_raw));
    wire push=valid && point_valid && confidence>=10 && distance_mm>=60 && distance_mm<=12000 && count<64;
    wire pop=valid && state==0 && count!=0;
    a741_sincos trig(.clk(clk),.rst_n(rst_n),.start(launch),.angle(trig_angle),.busy(busy),.done(done),.cosine(c),.sine(s));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            wr<=0;rd<=0;count<=0;state<=0;launch<=0;trig_angle<=0;angle<=0;range_q<=0;previous_angle<=0;
            have_previous<=0;px<=0;py<=0;ox<=0;oy<=0;h<=0;ex<=0;ey<=0;mx<=0;my<=0;
            normalized<=0;convert_start<=0;point_done<=0;scan_end<=0;overflow<=0;endpoint_x<=0;endpoint_y<=0;
            origin_x<=0;origin_y<=0;body_angle_cdeg<=0;range_mm<=0;
        end else begin
            launch<=0;convert_start<=0;point_done<=0;scan_end<=0;
            if(!valid) begin wr<=0;rd<=0;count<=0;state<=0;have_previous<=0;end
            else begin
                if(push) begin fifo[wr]<={confidence,angle_cdeg,distance_mm};wr<=wr+1'b1;end
                if(point_valid && count==64) overflow<=1;
                case({push,pop})
                    2'b10:count<=count+1'b1;
                    2'b01:count<=count-1'b1;
                    default:;
                endcase
                case(state)
                    0:if(pop && !busy) begin
                        angle<=fifo[rd][31:16];range_q<=fifo[rd][15:0];rd<=rd+1'b1;
                        px<=pose_x;py<=pose_y;h<=heading;ex<=offset_x;ey<=offset_y;
                        trig_angle<=heading;launch<=1;state<=1;
                    end
                    1:if(done) begin mx<=$signed(ex)*c-$signed(ey)*s;my<=$signed(ex)*s+$signed(ey)*c;state<=2;end
                    2:begin
                        ox<=px+(mx>>>15);oy<=py+(my>>>15);
                        normalized<=clockwise ? zero_cdeg+36000-angle:zero_cdeg+angle;
                        state<=3;
                    end
                    3:begin
                        if(normalized>=36000) normalized<=normalized-36000;
                        else begin
                            body_angle_cdeg<=normalized[15:0];
                            convert_start<=1;state<=6;
                        end
                    end
                    4:if(done) begin mx<=$signed({1'b0,range_q})*c;my<=$signed({1'b0,range_q})*s;state<=5;end
                    5:begin
                        endpoint_x<=ox+(mx>>>15);endpoint_y<=oy+(my>>>15);origin_x<=ox;origin_y<=oy;
                        range_mm<=range_q;point_done<=1;
                        scan_end<=have_previous && angle<previous_angle && previous_angle-angle>18000;
                        previous_angle<=angle;have_previous<=1;state<=0;
                    end
                    6:if(convert_done) begin trig_angle<=h+angle_raw[15:0];launch<=1;state<=4;end
                    default:state<=0;
                endcase
            end
        end
endmodule
`default_nettype wire
