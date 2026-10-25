`timescale 1ns/1ps
`default_nettype none
module safety_supervisor(
    input wire clk,rst_n,ms_tick,
    input wire stop,start,clear_fault,set_mode,mode_request,manual_arm,manual_update,manual_refresh,heartbeat,
    input wire [15:0] manual_ttl,
    input wire signed [31:0] manual_left,manual_right,
    input wire line_update,input wire [1:0] regions_valid,
    input wire signed [31:0] line_left,line_right,
    input wire tof_update,tof_valid,tof_error,input wire [15:0] distance_mm,front_offset_mm,
    input wire video_ready,input wire [15:0] motor_faults,
    output reg auto_mode,armed, output wire drive_enable,
    output wire signed [31:0] left_target,right_target,
    output reg [7:0] reason, output wire [7:0] state_code,
    output reg [15:0] line_age,tof_age,command_age,
    output reg [15:0] clearance, output wire [15:0] base_speed,
    output reg [1:0] safe_samples
);
    // reason: 0 none,1 operator stop,2 obstacle,3 line lost,4 camera stale,
    // 5 ToF invalid/stale,6 motor feedback,7 TTL,8 video unavailable.
    reg line_ok,tof_ok;reg [15:0] lost_ms,ttl_q;
    reg signed [31:0] ml,mr;
    wire [15:0] fresh_clearance=distance_mm>front_offset_mm ? distance_mm-front_offset_mm:16'd0;
    wire tof_usable=tof_ok && tof_age<150 && !tof_error && !(tof_update && !tof_valid);
    wire line_usable=line_ok && line_age<150 && !(line_update && regions_valid==0);
    wire obstacle=tof_update && tof_valid && fresh_clearance<=250;
    wire urgent=stop || obstacle || clearance<=250 || !tof_usable || motor_faults!=0 ||
        (auto_mode && (!line_usable || !video_ready)) ||
        (!auto_mode && command_age>=ttl_q);
    assign drive_enable=armed && reason==0 && !urgent;
    wire signed [31:0] manual_limit=clearance<500 ? $signed({16'd0,base_speed}):32'sd150;
    wire signed [31:0] safe_ml=ml>manual_limit ? manual_limit:ml < -manual_limit ? -manual_limit:ml;
    wire signed [31:0] safe_mr=mr>manual_limit ? manual_limit:mr < -manual_limit ? -manual_limit:mr;
    assign left_target=drive_enable ? (auto_mode ? line_left:safe_ml):32'sd0;
    assign right_target=drive_enable ? (auto_mode ? line_right:safe_mr):32'sd0;
    assign state_code=reason>=3 ? 8'd3:!armed ? 8'd0:
        drive_enable && (left_target!=0 || right_target!=0) ? 8'd2:8'd1;
    assign base_speed=clearance>=500 ? 16'd100:clearance<=250 ? 16'd0:
        16'd40+((clearance-16'd250)*16'd60)/16'd250;
    function signed [31:0] clamp;
        input signed [31:0] value;
        begin clamp=value>150 ? 32'sd150:value < -150 ? -32'sd150:value;end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            auto_mode<=0;armed<=0;reason<=0;line_age<=65535;tof_age<=65535;
            command_age<=0;lost_ms<=0;line_ok<=0;tof_ok<=0;safe_samples<=0;
            clearance<=0;ml<=0;mr<=0;ttl_q<=250;
        end else begin
            if(ms_tick) begin
                if(line_age!=65535) line_age<=line_age+1'b1;
                if(tof_age!=65535) tof_age<=tof_age+1'b1;
                if(command_age!=65535) command_age<=command_age+1'b1;
                if(!line_usable) begin if(lost_ms<100) lost_ms<=lost_ms+1'b1;end
                else lost_ms<=0;
            end
            if(line_update) begin line_age<=0;line_ok<=regions_valid!=0;end
            if(tof_update) begin
                tof_ok<=tof_valid;
                if(tof_valid) begin
                    tof_age<=0;clearance<=fresh_clearance;
                    if(fresh_clearance>400) begin if(safe_samples<3) safe_samples<=safe_samples+1'b1;end
                    else safe_samples<=0;
                end else safe_samples<=0;
            end
            if(!tof_usable && !(tof_update && tof_valid && fresh_clearance>400)) safe_samples<=0;
            if(clear_fault && !armed) reason<=0;
            if(set_mode) begin auto_mode<=mode_request;armed<=0;ml<=0;mr<=0;command_age<=0;end
            if(manual_arm && !auto_mode && reason<=1 && safe_samples==3 && tof_usable && motor_faults==0) begin armed<=1;command_age<=0;reason<=0;end
            if(start && auto_mode && (reason==0 || reason==1 || reason==2 || reason==3) &&
               safe_samples==3 && tof_usable && line_usable && video_ready && motor_faults==0) begin
                armed<=1;reason<=0;lost_ms<=0;
            end
            if(manual_update && !auto_mode && armed) begin
                ml<=clamp(manual_left);mr<=clamp(manual_right);
            end
            if(manual_refresh && !auto_mode && armed) begin
                command_age<=0;
                ttl_q<=manual_ttl==0 ? 16'd250:manual_ttl>1000 ? 16'd1000:manual_ttl;
            end
            if(heartbeat && !auto_mode && armed) command_age<=0;
            // Confirmation latches are independent of PC heartbeats in AUTO.
            if(armed) begin
                if(obstacle) begin reason<=2;armed<=0;end
                else if(!tof_usable) begin reason<=5;armed<=0;end
                else if(motor_faults!=0) begin reason<=6;armed<=0;end
                else if(auto_mode && !video_ready) begin reason<=8;armed<=0;end
                else if(auto_mode && line_age>=150) begin reason<=4;armed<=0;end
                else if(auto_mode && lost_ms>=99 && !line_usable) begin reason<=3;armed<=0;end
                else if(!auto_mode && command_age>=ttl_q) begin reason<=7;armed<=0;end
            end
            if(stop) begin
                armed<=0;ml<=0;mr<=0;
                if(reason<3 && !(armed && (!tof_usable || motor_faults!=0 ||
                   (auto_mode && (!video_ready || line_age>=150 || (lost_ms>=99 && !line_usable))) ||
                   (!auto_mode && command_age>=ttl_q)))) reason<=1;
            end
            // Mode change cancels simultaneous commands from the old owner.
            if(set_mode) begin armed<=0;ml<=0;mr<=0;end
        end
endmodule
`default_nettype wire
