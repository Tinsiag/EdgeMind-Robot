`timescale 1ns/1ps
`default_nettype none
module line_pd #(parameter WIDTH=800)(
    input wire clk,rst_n,update, input wire [1:0] regions_valid,
    input wire [10:0] near_center,far_center, input wire mirror,
    input wire [15:0] kp_q8,kd_q8,base_speed,
    output reg signed [31:0] left_target,right_target
);
    integer center,err,heading,turn,base,l,r;
    // Spatial derivative between far and near ROIs; deterministic per frame,
    // with no time-derivative spike after dropped frames.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin left_target<=0;right_target<=0;end
        else if(update) begin
            if(regions_valid==0) begin left_target<=0;right_target<=0;end
            else begin
                center=regions_valid[0] ? near_center:far_center;
                err=center-WIDTH/2;
                heading=regions_valid==3 ? $signed({1'b0,far_center})-$signed({1'b0,near_center}):0;
                if(mirror) begin err=-err;heading=-heading;end
                turn=(err*$signed({1'b0,kp_q8})+heading*$signed({1'b0,kd_q8})) >>> 8;
                if(turn>60) turn=60;if(turn < -60) turn=-60;
                base=base_speed>100 ? 100:base_speed;
                if(regions_valid!=3 || err>100 || err < -100 || turn>30 || turn < -30)
                    if(base>40) base=40;
                l=base+turn;r=base-turn; // line to image right => right turn
                if(l<0) l=0;if(r<0) r=0;if(l>150) l=150;if(r>150) r=150;
                left_target<=l;right_target<=r;
            end
        end
endmodule
`default_nettype wire
