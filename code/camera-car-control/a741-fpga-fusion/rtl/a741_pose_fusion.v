`timescale 1ns/1ps
`default_nettype none
// FRACTION_BITS=16 accepts Q16 millimetres from the encoder conversion stage.
module a741_pose_fusion #(parameter FRACTION_BITS=0)(
    input wire clk,rst_n,tick,sample_valid,pose_set,
    input wire signed [31:0] left_distance_mm,right_distance_mm,
    input wire signed [15:0] yaw,set_heading,
    input wire signed [31:0] set_x_mm,set_y_mm,
    output wire signed [31:0] x_mm,y_mm,
    output reg signed [15:0] heading,
    output reg pose_valid,overrun
);
    reg [2:0] state;
    reg launch;wire trig_done,trig_busy;wire signed [17:0] c,s;
    reg signed [15:0] imu_origin,map_origin,angle;
    wire signed [15:0] world_yaw=yaw-imu_origin+map_origin;
    reg signed [32:0] distance_q;
    reg signed [63:0] x_q,y_q,dx,dy;
    wire signed [50:0] product_x=distance_q*c,product_y=distance_q*s;
    assign x_mm=x_q>>>16;assign y_mm=y_q>>>16;
    a741_sincos trig(.clk(clk),.rst_n(rst_n),.start(launch),.angle(angle),
        .busy(trig_busy),.done(trig_done),.cosine(c),.sine(s));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=0;launch<=0;imu_origin<=0;map_origin<=0;angle<=0;distance_q<=0;
            x_q<=0;y_q<=0;dx<=0;dy<=0;heading<=0;pose_valid<=0;overrun<=0;
        end else begin
            launch<=0;
            if(!sample_valid) begin state<=0;pose_valid<=0;end
            else if(pose_set) begin
                state<=0;imu_origin<=yaw;map_origin<=set_heading;angle<=set_heading;heading<=set_heading;
                x_q<=$signed({{32{set_x_mm[31]}},set_x_mm})<<<16;
                y_q<=$signed({{32{set_y_mm[31]}},set_y_mm})<<<16;pose_valid<=1;
            end else case(state)
                0:if(tick && !trig_busy) begin
                    distance_q<=($signed({left_distance_mm[31],left_distance_mm})+$signed({right_distance_mm[31],right_distance_mm}))>>>1;
                    angle<=world_yaw;heading<=world_yaw;launch<=1;state<=1;
                end
                1:if(trig_done) begin
                    if(FRACTION_BITS==0) begin dx<=$signed(product_x)<<<1;dy<=$signed(product_y)<<<1;end
                    else begin dx<=$signed(product_x)>>>(FRACTION_BITS-1);dy<=$signed(product_y)>>>(FRACTION_BITS-1);end
                    state<=2;
                end
                2:begin x_q<=x_q+dx;y_q<=y_q+dy;pose_valid<=1;state<=0;end
                default:state<=0;
            endcase
            if(tick && state!=0) overrun<=1;
        end
endmodule
`default_nettype wire
