`timescale 1ns/1ps
`default_nettype none
// Bounded correlative matching around the predicted pose: +/-50mm, +/-3deg.
// A scan contributes up to 64 decimated endpoints. No global localization.
module a741_scan_match(
    input wire clk,rst_n,ms_tick,enable,cancel,point_valid,scan_end,
    input wire signed [31:0] endpoint_x,endpoint_y,pose_x,pose_y,
    output reg busy,map_read,output reg [13:0] map_address,
    input wire map_done,input wire [1:0] map_value,
    output reg result_valid,accepted,localized,
    output reg signed [15:0] correction_x,correction_y,correction_yaw,
    output reg [7:0] quality
);
    reg signed [15:0] points_x[0:63],points_y[0:63];
    reg signed [15:0] point_x_q,point_y_q;
    reg [6:0] count,index,samples;reg [2:0] decimate;
    reg [4:0] candidate;reg [3:0] state;
    reg signed [31:0] origin_x,origin_y,tx,ty,gx,gy;
    wire [12:0] tx_grid=tx[12:0],ty_grid=ty[12:0];
    reg signed [15:0] offset_x,offset_y,offset_yaw,best_x,best_y,best_yaw;
    reg [7:0] score,best_score,second_score;
    reg [15:0] age;reg [1:0] good_scans,bad_scans;
    reg launch;wire trig_busy,trig_done;wire signed [17:0] c,s;
    reg signed [47:0] px,py;
    reg quality_start;wire quality_busy,quality_done;wire [31:0] quality_value;
    a741_divider quality_divider(.clk(clk),.rst_n(rst_n),.cancel(cancel || !enable),.start(quality_start),
        .numerator({24'd0,best_score}*32'd100),.denominator({9'd0,samples}),.busy(quality_busy),.done(quality_done),.quotient(quality_value));
    a741_sincos trig(.clk(clk),.rst_n(rst_n),.start(launch),.angle(offset_yaw),.busy(trig_busy),.done(trig_done),.cosine(c),.sine(s));
    // Registered reads map the scan cache to RAM instead of 2048 flip-flops
    // and large combinational multiplexers feeding the multipliers.
    always @(posedge clk) begin
        point_x_q<=points_x[index[5:0]];point_y_q<=points_y[index[5:0]];
        if(rst_n && !cancel && enable && state==0 && point_valid && !scan_end && decimate==0 && count<64) begin
            points_x[count[5:0]]<=endpoint_x-pose_x;
            points_y[count[5:0]]<=endpoint_y-pose_y;
        end
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            busy<=0;map_read<=0;map_address<=0;result_valid<=0;accepted<=0;localized<=0;
            correction_x<=0;correction_y<=0;correction_yaw<=0;quality<=0;
            count<=0;index<=0;samples<=0;decimate<=0;candidate<=0;state<=0;
            origin_x<=0;origin_y<=0;tx<=0;ty<=0;gx<=0;gy<=0;offset_x<=0;offset_y<=0;offset_yaw<=0;
            best_x<=0;best_y<=0;best_yaw<=0;score<=0;best_score<=0;second_score<=0;
            age<=65535;good_scans<=0;bad_scans<=0;launch<=0;quality_start<=0;px<=0;py<=0;
        end else begin
            map_read<=0;result_valid<=0;launch<=0;quality_start<=0;
            if(ms_tick) begin if(age!=65535) age<=age+1'b1;if(age>=400) localized<=0;end
            if(cancel || !enable) begin count<=0;state<=0;busy<=0;localized<=0;good_scans<=0;bad_scans<=0;end
            else case(state)
                0:if(point_valid) begin
                    decimate<=decimate+1'b1;
                    if(scan_end) begin
                        if(count>=16 && !trig_busy) begin
                            samples<=count;count<=0;candidate<=0;score<=0;best_score<=0;second_score<=0;
                            origin_x<=pose_x;origin_y<=pose_y;busy<=1;state<=1;
                        end else count<=0;
                    end else if(decimate==0 && count<64) begin
                        count<=count+1'b1;
                    end
                end
                1:begin
                    offset_x<=($signed({1'b0,candidate%5'd3})-1)*50;
                    offset_y<=($signed({1'b0,(candidate/5'd3)%5'd3})-1)*50;
                    offset_yaw<=($signed({1'b0,candidate/5'd9})-1)*546;
                    index<=0;score<=0;state<=2;
                end
                2:begin launch<=1;state<=3;end
                3:if(trig_done) state<=4;
                4:state<=13;
                13:begin
                    px<=$signed(point_x_q)*c-$signed(point_y_q)*s;
                    py<=$signed(point_x_q)*s+$signed(point_y_q)*c;state<=5;
                end
                5:begin tx<=origin_x+offset_x+(px>>>15)+3200;ty<=origin_y+offset_y+(py>>>15)+3200;state<=6;end
                6:begin gx<={24'd0,8'(tx_grid/13'd50)};gy<={24'd0,8'(ty_grid/13'd50)};state<=7;end
                7:if(tx<0 || ty<0 || tx>=6400 || ty>=6400 || gx>127 || gy>127) state<=9;
                    else begin map_address<={gy[6:0],gx[6:0]};map_read<=1;state<=8;end
                8:if(map_done) begin if(map_value==2'b10) score<=score+1'b1;state<=9;end
                9:if(index+1>=samples) state<=10;
                    else begin index<=index+1'b1;state<=4;end
                10:begin
                    if(score>best_score || (score==best_score && candidate==13)) begin
                        second_score<=best_score;best_score<=score;best_x<=offset_x;best_y<=offset_y;best_yaw<=offset_yaw;
                    end else if(score>second_score) second_score<=score;
                    if(candidate==26) state<=11;
                    else begin candidate<=candidate+1'b1;state<=1;end
                end
                11:begin quality_start<=1;state<=12;end
                12:if(quality_done) begin
                    result_valid<=1;busy<=0;state<=0;age<=0;quality<=quality_value[7:0];
                    // Even a strong zero-offset alias is unsafe when several poses tie.
                    accepted<=best_score*100>=samples*60 && best_score>=second_score+2;
                    if(best_score*100>=samples*60 && best_score>=second_score+2) begin
                        correction_x<=best_x;correction_y<=best_y;correction_yaw<=best_yaw;bad_scans<=0;
                        if(good_scans<3) good_scans<=good_scans+1'b1;
                        if(good_scans>=1) localized<=1;
                    end else begin
                        good_scans<=0;if(bad_scans<3) bad_scans<=bad_scans+1'b1;
                        if(bad_scans>=1) localized<=0;
                    end
                end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
