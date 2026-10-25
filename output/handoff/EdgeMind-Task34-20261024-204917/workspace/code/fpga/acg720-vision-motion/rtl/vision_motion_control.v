`timescale 1ns/1ps
`default_nettype none
module vision_motion_control #(parameter CLK_HZ=50000000,PWM_HZ=1000)(
    input wire clk,rst_n,uart_rx,output wire uart_tx,
    input wire left_a,left_b,right_a,right_b,
    input wire line_update,input wire [1:0] regions_valid,input wire [10:0] near_center,far_center,
    input wire [15:0] line_frame_id,
    input wire tof_update,tof_valid,tof_error,input wire [15:0] distance_mm,
    input wire [7:0] range_status,input wire video_ready,video_error,
    input wire [1:0] video_warning,
    output wire left_in1,left_in2,right_in1,right_in2,
    output reg [7:0] threshold,
    output reg [10:0] near_y0,near_y1,far_y0,far_y1,
    output wire [191:0] osd_status,output wire [7:0] led,
    output wire ms_tick
);
    wire [7:0] rx_data;wire rx_valid;
    uart_rx #(.CLK_HZ(CLK_HZ)) rx(.clk(clk),.rstn(rst_n),.rx(uart_rx),.data(rx_data),.valid(rx_valid),.framing_error());
    wire cmd_valid;wire [7:0] kind,seq,length;wire [15:0] ttl;wire [255:0] payload;
    vision_protocol #(.CLK_HZ(CLK_HZ)) parser(.clk(clk),.rstn(rst_n),.rx_data(rx_data),.rx_valid(rx_valid),.cmd_valid(cmd_valid),.cmd_length(length),.cmd_type(kind),.cmd_seq(seq),.cmd_ttl_ms(ttl),.cmd_payload(payload),.crc_error(),.length_error());
    reg [15:0] kp,kd,front_offset,output_limit,ramp_limit;
    reg mirror;reg [31:0] cpr_l,cpr_r,diam_l,diam_r,wheel_base,max_speed,counts_deg;
    reg [7:0] protocol_errors;reg length_ok,param_ok,line_param_ok;
    wire auto_mode,armed,drive_enable;wire [7:0] reason,state_code;
    wire [15:0] line_age,tof_age,command_age,clearance,base_speed,motor_faults;
    wire [1:0] safe_samples;
    wire signed [31:0] lc,rc,ls,rs,tl,tr;
    wire [15:0] lp,rp;wire [31:0] li,ri;wire control_tick;
    wire [31:0] value=payload[39:8];
    always @* begin
        length_ok=0;param_ok=1;line_param_ok=1;
        case(kind)
            8'h01,8'h02,8'h03,8'h04,8'h05,8'h20,8'h21,8'h40,8'h42,8'h43:length_ok=length==0;
            8'h10,8'h11:length_ok=length==8;
            8'h12:length_ok=length==6;
            8'h30,8'h44:length_ok=length==5;
            8'h41:length_ok=length==1 && payload[7:0]<=1;
            default:length_ok=0;
        endcase
        case(payload[7:0])
            0,1:param_ok=value>=100 && value<=100000;
            2,3:param_ok=value>=10 && value<=500;
            4:param_ok=value>=20 && value<=1000;
            5:param_ok=value>=40 && value<=400;
            6:param_ok=value>=1 && value<=100000;
            9:param_ok=value<=512;
            10:param_ok=value>=1 && value<=100;
            default:param_ok=0;
        endcase
        case(payload[7:0])
            0:line_param_ok=value>=1 && value<=254;
            1:line_param_ok=value<=near_y1 && value<480;
            2:line_param_ok=value>=near_y0 && value<480;
            3:line_param_ok=value<=far_y1 && value<480;
            4:line_param_ok=value>=far_y0 && value<480;
            5:line_param_ok=value<=1;
            6,7:line_param_ok=value<=1024;
            8:line_param_ok=value<=500;
            default:line_param_ok=0;
        endcase
    end
    wire accepted=cmd_valid && length_ok &&
        (kind!=8'h30 || (param_ok && (!armed || (!auto_mode && (payload[7:0]==9 || payload[7:0]==10))))) &&
        (kind!=8'h44 || (!armed && line_param_ok)) &&
        (kind!=8'h12 || (payload[47:32]>=20 && payload[47:32]<=150 && $signed(payload[31:0])>=-360000 && $signed(payload[31:0])<=360000));
    wire stop=accepted && (kind==8'h03 || kind==8'h04);
    wire clear_fault=accepted && kind==8'h21 && !armed;
    wire signed [31:0] line_l,line_r,twist_l,twist_r,rotate_l,rotate_r;
    wire rotate_active,rotate_done;reg rotate_start;reg signed [31:0] angle_q;reg [15:0] rotate_speed_q;
    wire manual_update=accepted && (kind==8'h10 || kind==8'h11) && !auto_mode;
    // Restore READY by feeding zero wheel targets when rotation completes.
    wire motion_update=manual_update || rotate_active || rotate_done;
    wire signed [31:0] manual_l=rotate_done ? 32'sd0:rotate_active ? rotate_l:kind==8'h10 ? twist_l:$signed(payload[31:0]);
    wire signed [31:0] manual_r=rotate_done ? 32'sd0:rotate_active ? rotate_r:kind==8'h10 ? twist_r:$signed(payload[63:32]);
    differential_drive diff(.v_mm_s(payload[31:0]),.omega_mrad_s(payload[47:32]),.wheel_base_mm(wheel_base[15:0]),.max_speed_mm_s(max_speed>150?32'd150:max_speed),.left_speed(twist_l),.right_speed(twist_r));
    rotate_controller rot(.clk(clk),.rstn(rst_n),.start(rotate_start),.cancel(!armed || auto_mode || stop || manual_update || (accepted && kind==8'h41)),.angle_mdeg(angle_q),.max_speed({16'd0,rotate_speed_q}),.left_count(lc),.right_count(rc),.left_speed(ls),.right_speed(rs),.counts_per_degree_q16(counts_deg),.tolerance_counts(32'd4),.active(rotate_active),.done(rotate_done),.left_target(rotate_l),.right_target(rotate_r));
    line_pd pd(.clk(clk),.rst_n(rst_n),.update(line_update || control_tick),.regions_valid(regions_valid),.near_center(near_center),.far_center(far_center),.mirror(mirror),.kp_q8(kp),.kd_q8(kd),.base_speed(base_speed),.left_target(line_l),.right_target(line_r));
    safety_supervisor safety(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.stop(stop),.start(accepted && kind==8'h42),.clear_fault(clear_fault),.set_mode(accepted && kind==8'h41),.mode_request(payload[0]),.manual_arm(accepted && kind==8'h02),.manual_update(motion_update),.manual_refresh(accepted && (kind==8'h10 || kind==8'h11 || kind==8'h12)),.heartbeat(accepted && kind==8'h05),.manual_ttl(ttl),.manual_left(manual_l),.manual_right(manual_r),.line_update(line_update),.regions_valid(regions_valid),.line_left(line_l),.line_right(line_r),.tof_update(tof_update),.tof_valid(tof_valid),.tof_error(tof_error),.distance_mm(distance_mm),.front_offset_mm(front_offset),.video_ready(video_ready && !video_error),.motor_faults(motor_faults),.auto_mode(auto_mode),.armed(armed),.drive_enable(drive_enable),.left_target(tl),.right_target(tr),.reason(reason),.state_code(state_code),.line_age(line_age),.tof_age(tof_age),.command_age(command_age),.clearance(clearance),.base_speed(base_speed),.safe_samples(safe_samples));
    motion_core #(.CLK_HZ(CLK_HZ),.PWM_HZ(PWM_HZ)) core(.clk(clk),.rst_n(rst_n),.enable(drive_enable),.clear_fault(clear_fault),.left_a(left_a),.left_b(left_b),.right_a(right_a),.right_b(right_b),.left_target(tl),.right_target(tr),.output_limit(output_limit),.ramp_limit(ramp_limit),.cpr_l(cpr_l),.cpr_r(cpr_r),.diam_l(diam_l),.diam_r(diam_r),.left_in1(left_in1),.left_in2(left_in2),.right_in1(right_in1),.right_in2(right_in2),.left_count(lc),.right_count(rc),.left_speed(ls),.right_speed(rs),.left_pwm(lp),.right_pwm(rp),.faults(motor_faults),.left_invalid_count(li),.right_invalid_count(ri),.ms_tick(ms_tick),.control_tick(control_tick));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            threshold<=80;near_y0<=360;near_y1<=399;far_y0<=260;far_y1<=299;
            kp<=64;kd<=96;mirror<=0;front_offset<=0;output_limit<=512;ramp_limit<=50;
            cpr_l<=1469;cpr_r<=1471;diam_l<=66;diam_r<=66;wheel_base<=121;max_speed<=150;counts_deg<=491;
            protocol_errors<=0;rotate_start<=0;angle_q<=0;rotate_speed_q<=40;
        end else begin
            rotate_start<=0;
            if(cmd_valid && !accepted && protocol_errors!=255) protocol_errors<=protocol_errors+1'b1;
            if(accepted && kind==8'h12 && !auto_mode && armed && !rotate_active) begin rotate_start<=1;angle_q<=payload[31:0];rotate_speed_q<=payload[47:32];end
            if(accepted && kind==8'h30) case(payload[7:0])
                0:cpr_l<=value;1:cpr_r<=value;2:diam_l<=value;3:diam_r<=value;
                4:wheel_base<=value;5:max_speed<=value;6:counts_deg<=value;
                9:output_limit<=value[15:0];10:ramp_limit<=value[15:0];default:;
            endcase
            if(accepted && kind==8'h44) case(payload[7:0])
                0:threshold<=value[7:0];1:near_y0<=value[10:0];2:near_y1<=value[10:0];
                3:far_y0<=value[10:0];4:far_y1<=value[10:0];5:mirror<=value[0];
                6:kp<=value[15:0];7:kd<=value[15:0];8:front_offset<=value[15:0];default:;
            endcase
        end
    reg [255:0] reply_payload;reg [7:0] reply_type,reply_length;
    wire reply_ready;
    always @* begin
        reply_payload=0;reply_type=8'h80;reply_length=25;
        reply_payload[7:0]=rotate_active?8'd2:state_code;
        reply_payload[23:8]=motor_faults | ((reason>=3)?16'h0100:16'h0000);
        reply_payload[55:24]=lc;reply_payload[87:56]=rc;reply_payload[119:88]=ls;reply_payload[151:120]=rs;
        reply_payload[167:152]=lp;reply_payload[183:168]=rp;reply_payload[199:184]=command_age;
        if(kind==8'h40) begin
            reply_type=8'hc0;reply_length=8;reply_payload=0;
            reply_payload[31:0]=32'h314d5645; // ASCII EVM1
            reply_payload[47:32]=16'h000f; // bridge fixed, autonomous, sensing, config
            reply_payload[63:48]=16'd150;
        end else if(kind==8'h43) begin
            reply_type=8'hc3;reply_length=32;reply_payload=0;
            reply_payload[7:0]={6'd0,armed,auto_mode};reply_payload[15:8]=reason;
            reply_payload[31:16]=distance_mm;reply_payload[47:32]=clearance;
            reply_payload[55:48]=range_status;
            reply_payload[63:56]={1'b0,video_warning,video_ready,video_error,tof_error,tof_valid,1'b0};
            reply_payload[79:64]=line_age;reply_payload[95:80]=tof_age;
            reply_payload[111:96]={5'd0,near_center};reply_payload[127:112]={5'd0,far_center};
            reply_payload[135:128]={6'd0,regions_valid};reply_payload[143:136]=protocol_errors;
            reply_payload[159:144]=line_frame_id;reply_payload[191:160]=li;reply_payload[223:192]=ri;
            reply_payload[239:224]=output_limit;reply_payload[255:240]=base_speed;
        end
    end
    vision_packet_tx #(.CLK_HZ(CLK_HZ)) tx(.clk(clk),.rst_n(rst_n),.request(accepted && reply_ready && kind!=8'h05 && kind!=8'h10 && kind!=8'h11),.kind(reply_type),.seq(seq),.length(reply_length),.payload(reply_payload),.ready(reply_ready),.tx(uart_tx));
    assign osd_status={61'd0,state_code,reason,rs[15:0],ls[15:0],clearance,auto_mode,far_y1,far_y0,near_y1,near_y0,far_center,near_center};
    assign led={auto_mode,reason>=3,tof_error,video_error,reason==2,armed,drive_enable,rst_n};
endmodule
`default_nettype wire
