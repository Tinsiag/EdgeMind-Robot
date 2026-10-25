`timescale 1ns/1ps
`default_nettype none
// Goal-to-start path stack, heading-aware point tracking at 100Hz.
module a741_path_tracker #(parameter TRACK_MM=234)(
    input wire clk,rst_n,tick,load_begin,load_valid,load_last,
    input wire [6:0] load_x,load_y,
    input wire enable,cancel,input wire [9:0] speed_limit,
    input wire signed [31:0] pose_x,pose_y,input wire signed [15:0] heading,goal_heading,
    output reg signed [31:0] left_target,right_target,
    output reg route_ready,arrived,fault,
    output wire [14:0] remaining
);
    // Each path edge is an adjacent-cell direction, not a repeated XY address.
    reg [3:0] route[0:16383];reg [14:0] count,index;
    reg [3:0] route_q;
    wire signed [7:0] step_x={{6{route_q[1]}},route_q[1:0]};
    wire signed [7:0] step_y={{6{route_q[3]}},route_q[3:2]};
    reg [6:0] previous_x,previous_y,current_x,current_y;
    wire signed [8:0] load_dx=$signed({1'b0,previous_x})-$signed({1'b0,load_x});
    wire signed [8:0] load_dy=$signed({1'b0,previous_y})-$signed({1'b0,load_y});
    reg [3:0] state;reg launch;reg [15:0] angle;
    wire busy,done;wire signed [17:0] c,s;
    reg signed [31:0] dx,dy,forward,left,correction,linear;
    reg signed [63:0] dot,cross_product;
    reg [31:0] distance_l1;
    reg signed [15:0] yaw_error;
    reg [9:0] cap;
    reg [8:0] cap_scaled;
    reg [6:0] cap_cached;
    reg div_start;reg [31:0] numerator;reg [15:0] denominator;reg negative;
    reg [31:0] abs_left;
    reg [63:0] steering_product;
    wire div_busy,div_done;wire [31:0] quotient;
    function signed [31:0] bounded(input signed [31:0] value,input [9:0] requested_limit);
        reg signed [31:0] maximum;
        begin
            maximum=requested_limit>100 ? 100:$signed({1'b0,requested_limit});
            bounded=value>maximum ? maximum:value< -maximum ? -maximum:value;
        end
    endfunction
    a741_divider divider(.clk(clk),.rst_n(rst_n),.cancel(cancel || !enable),.start(div_start),
        .numerator(numerator),.denominator(denominator),.busy(div_busy),.done(div_done),.quotient(quotient));
    always @(posedge clk) route_q<=route[index[13:0]];
    assign remaining=index;
    // Clamp before narrowing; the product is at most 300. Pipeline the
    // constant divide separately from obstacle range scaling.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin cap_scaled<=0;cap_cached<=0;end
        else begin
            cap_scaled<=speed_limit>10'd100 ? 9'd300:9'(speed_limit)*9'd3;
            cap_cached<=cap_scaled/9'd5;
        end
    a741_sincos trig(.clk(clk),.rst_n(rst_n),.start(launch),.angle(angle),.busy(busy),.done(done),.cosine(c),.sine(s));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            count<=0;index<=0;state<=0;launch<=0;angle<=0;dx<=0;dy<=0;forward<=0;left<=0;
            previous_x<=0;previous_y<=0;current_x<=0;current_y<=0;
            dot<=0;cross_product<=0;correction<=0;linear<=0;distance_l1<=0;yaw_error<=0;cap<=0;
            left_target<=0;right_target<=0;route_ready<=0;arrived<=0;fault<=0;div_start<=0;numerator<=0;denominator<=1;negative<=0;
            abs_left<=0;steering_product<=0;
        end else begin
            launch<=0;div_start<=0;
            if(load_begin) begin count<=0;index<=0;route_ready<=0;fault<=0;arrived<=0;state<=0;left_target<=0;right_target<=0;end
            else if(load_valid) begin
                if(count<16384 && (count==0 || (load_dx>=-1 && load_dx<=1 && load_dy>=-1 && load_dy<=1 && (load_dx!=0 || load_dy!=0)))) begin
                    route[count[13:0]]<=count==0 ? 4'd0:{load_dy[1:0],load_dx[1:0]};count<=count+1'b1;
                    previous_x<=load_x;previous_y<=load_y;
                    if(load_last) begin route_ready<=1;index<=count;current_x<=load_x;current_y<=load_y;end
                end else begin fault<=1;route_ready<=0;end
            end
            if(cancel || !enable || fault) begin state<=0;left_target<=0;right_target<=0;end
            else case(state)
                0:if(tick && route_ready && !arrived && !load_begin && !load_valid && !busy) begin
                    dx<=$signed({1'b0,current_x})*50-3175-pose_x;
                    dy<=$signed({1'b0,current_y})*50-3175-pose_y;
                    angle<=heading;yaw_error<=goal_heading-heading;
                    cap<={3'b0,cap_cached};launch<=1;state<=1;
                end
                1:if(done) begin dot<=$signed(dx)*c+$signed(dy)*s;cross_product<=-$signed(dx)*s+$signed(dy)*c;state<=2;end
                2:begin
                    forward<=dot>>>15;left<=cross_product>>>15;
                    distance_l1<=(dx<0 ? -dx:dx)+(dy<0 ? -dy:dy);state<=3;
                end
                3:begin
                    if(distance_l1<=75 && index!=0) begin
                        // Extend signed directions before adding to unsigned cell indices.
                        current_x<=7'($signed({1'b0,current_x})+step_x);
                        current_y<=7'($signed({1'b0,current_y})+step_y);
                        index<=index-1'b1;state<=0;
                    end
                    else if(distance_l1<=100 && index==0) begin
                        if(yaw_error<2731 && yaw_error> -2731) begin arrived<=1;left_target<=0;right_target<=0;state<=0;end
                        else begin left_target<=bounded(yaw_error>0 ? -40:40,speed_limit);right_target<=bounded(yaw_error>0 ? 40:-40,speed_limit);state<=0;end
                    end else begin
                        abs_left<=left<0 ? -left:left;negative<=left<0;
                        denominator<=distance_l1==0 ? 16'd1:distance_l1[15:0];
                        linear<=forward<=0 || (left>0 ? left:-left)>forward ? 0:cap;state<=6;
                    end
                end
                4:begin
                    // Reserve wheel-speed headroom while steering, with no reverse translation.
                    if(cap==0) begin left_target<=0;right_target<=0;end
                    else if(linear==0) begin left_target<=bounded(left>=0 ? -40:40,speed_limit);right_target<=bounded(left>=0 ? 40:-40,speed_limit);end
                    else begin
                        left_target<=bounded(linear-((correction>40) ? 40:(correction< -40) ? -40:correction),speed_limit);
                        right_target<=bounded(linear+((correction>40) ? 40:(correction< -40) ? -40:correction),speed_limit);
                    end
                    state<=0;
                end
                5:if(div_done) begin correction<=negative ? -$signed(quotient):$signed(quotient);state<=4;end
                // Separate absolute value, wheelbase multiplication and divide
                // launch. Unsigned shift also handles odd wheelbases exactly.
                6:begin steering_product<=abs_left*32'(TRACK_MM);state<=7;end
                7:begin numerator<=steering_product[32:1];div_start<=1;state<=5;end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
