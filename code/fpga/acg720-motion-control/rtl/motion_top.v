`timescale 1ns/1ps
`default_nettype none
module motion_top #(
    parameter integer CLK_HZ=50000000,
    parameter integer PWM_HZ=20000,
    parameter integer PI_LIMIT_DEFAULT=1000,
    parameter integer RAMP_LIMIT_DEFAULT=100,
    parameter integer CALIBRATED_DEFAULTS=0,
    parameter integer ENCODER_FAULT_ENABLE=1,
    parameter integer RIGHT_BRIDGE_INVERT=0,
    parameter integer MOTION_CAPABILITIES=0
)(
    input wire clk, input wire stop_n,
    input wire uart_rx, output wire uart_tx,
    input wire left_enc_a, left_enc_b, right_enc_a, right_enc_b,
    output wire left_in1, left_in2, right_in1, right_in2,
    output wire [7:0] led
);
    wire rstn=stop_n; wire [7:0] rx_byte; wire rx_valid;
    uart_rx #(.CLK_HZ(CLK_HZ)) u_rx(.clk(clk),.rstn(rstn),.rx(uart_rx),.data(rx_byte),.valid(rx_valid),.framing_error());
    wire cmd_valid, crc_error, length_error; wire [7:0] cmd_type, cmd_seq; wire [15:0] cmd_ttl; wire [255:0] payload;
    motion_protocol proto(.clk(clk),.rstn(rstn),.rx_data(rx_byte),.rx_valid(rx_valid),.cmd_valid(cmd_valid),.cmd_type(cmd_type),.cmd_seq(cmd_seq),.cmd_ttl_ms(cmd_ttl),.cmd_payload(payload),.crc_error(crc_error),.length_error(length_error));
    reg [31:0] ms_count; wire ms_tick=(ms_count==CLK_HZ/1000-1); reg [3:0] sample_div; wire sample_tick=ms_tick && (sample_div==9);
    always @(posedge clk or negedge rstn) if(!rstn) begin ms_count<=0; sample_div<=0; end else if(ms_tick) begin ms_count<=0; if(sample_div==9) sample_div<=0; else sample_div<=sample_div+1'b1; end else ms_count<=ms_count+1'b1;
    wire signed [1:0] left_step,right_step; wire left_invalid,right_invalid;
    quadrature_decoder ql(.clk(clk),.rstn(rstn),.a(left_enc_a),.b(left_enc_b),.invert(1'b0),.step(left_step),.invalid(left_invalid));
    // Hand-turn verified 2026-10-14: forward is negative on raw right AB.
    quadrature_decoder qr(.clk(clk),.rstn(rstn),.a(right_enc_a),.b(right_enc_b),.invert(1'b1),.step(right_step),.invalid(right_invalid));
    wire signed [31:0] left_count,right_count,left_delta,right_delta; wire [31:0] li,ri; wire lto,rto;
    wire monitor_l,monitor_r;
    encoder_counter el(.clk(clk),.rstn(rstn),.step(left_step),.invalid_step(left_invalid),.sample_tick(sample_tick),.monitor_enable(monitor_l),.count(left_count),.delta(left_delta),.invalid_count(li),.feedback_timeout(lto));
    encoder_counter er(.clk(clk),.rstn(rstn),.step(right_step),.invalid_step(right_invalid),.sample_tick(sample_tick),.monitor_enable(monitor_r),.count(right_count),.delta(right_delta),.invalid_count(ri),.feedback_timeout(rto));
    reg [31:0] cpr_l,cpr_r,diam_l,diam_r,wheel_base,max_speed,counts_deg; reg [6:0] params_valid;
    reg signed [31:0] target_l,target_r; reg signed [31:0] pending_v,pending_omega; reg twist_pending; reg armed; reg [7:0] state_code; reg [15:0] faults; reg [15:0] command_age; reg [15:0] command_ttl; reg rotate_start;
    reg [15:0] pi_limit,ramp_limit;
    wire signed [31:0] speed_l,speed_r; wire speed_l_valid,speed_r_valid;
    reg signed [31:0] speed_l_ctrl, speed_r_ctrl;
    wheel_speed_estimator sl(.clk(clk),.rstn(rstn),.sample_tick(sample_tick),.delta_count(left_delta),.cpr(cpr_l),.diameter_mm(diam_l),.speed_mm_s(speed_l),.valid(speed_l_valid));
    wheel_speed_estimator sr(.clk(clk),.rstn(rstn),.sample_tick(sample_tick),.delta_count(right_delta),.cpr(cpr_r),.diameter_mm(diam_r),.speed_mm_s(speed_r),.valid(speed_r_valid));
    always @(posedge clk or negedge rstn) begin
        if(!rstn) begin speed_l_ctrl<=0; speed_r_ctrl<=0; end
        else if(sample_tick) begin speed_l_ctrl<=speed_l; speed_r_ctrl<=speed_r; end
    end
    wire signed [31:0] twist_l,twist_r; differential_drive diff(.v_mm_s(pending_v),.omega_mrad_s(pending_omega[15:0]),.wheel_base_mm(wheel_base[15:0]),.max_speed_mm_s(max_speed),.left_speed(twist_l),.right_speed(twist_r));
    wire rotate_active,rotate_done;
    wire stop_cmd=cmd_valid && (cmd_type==8'h03 || cmd_type==8'h04);
    wire timeout_fault=armed && (rotate_active || target_l!=0 || target_r!=0) && command_age>command_ttl;
    // A722 explicitly masks only the illegal-AB fault. Decoder behavior remains
    // unchanged: illegal transitions do not generate a count step.
    wire encoder_fault=(ENCODER_FAULT_ENABLE != 0) &&
        (left_invalid || right_invalid || li!=0 || ri!=0);
    assign monitor_l=armed && !faults && target_l!=0;
    assign monitor_r=armed && !faults && target_r!=0;
    wire feedback_fault=(monitor_l && lto) || (monitor_r && rto);
    wire fault_now=timeout_fault || encoder_fault || feedback_fault;
    wire control_enable=armed && !faults && !fault_now && !stop_cmd;
    wire rotate_cancel=!armed || faults!=0 || fault_now || stop_cmd ||
        (cmd_valid && (cmd_type==8'h10 || cmd_type==8'h11));
    reg signed [31:0] rotate_angle;
    reg [15:0] rotate_speed;
    wire signed [31:0] rotate_l,rotate_r;
    rotate_controller rot(.clk(clk),.rstn(rstn),.start(rotate_start),.cancel(rotate_cancel),.angle_mdeg(rotate_angle),.max_speed({16'b0,rotate_speed}),.left_count(left_count),.right_count(right_count),.left_speed(speed_l),.right_speed(speed_r),.counts_per_degree_q16(counts_deg),.tolerance_counts(4),.active(rotate_active),.done(rotate_done),.left_target(rotate_l),.right_target(rotate_r));
    wire control_update=sample_tick;
    wire signed [31:0] pi_l,pi_r; wire signed [31:0] applied_l,applied_r;
    wheel_pi_controller pil(.clk(clk),.rstn(rstn),.update(control_update),.enable(control_enable),.target_speed(target_l),.measured_speed(speed_l_ctrl),.output_limit(pi_limit),.ramp_limit(ramp_limit),.command(pi_l),.applied_target(applied_l));
    wheel_pi_controller pir(.clk(clk),.rstn(rstn),.update(control_update),.enable(control_enable),.target_speed(target_r),.measured_speed(speed_r_ctrl),.output_limit(pi_limit),.ramp_limit(ramp_limit),.command(pi_r),.applied_target(applied_r));
    wire [31:0] pwm_l,pwm_r;
    at8236_motor_driver #(.CLK_HZ(CLK_HZ),.PWM_HZ(PWM_HZ)) dl(.clk(clk),.rstn(rstn),.enable(control_enable),.command(pi_l),.in1(left_in1),.in2(left_in2),.pwm_abs(pwm_l));
    // Change physical bridge polarity AFTER PI. Positive target and positive
    // body-forward feedback remain in the same coordinate system.
    wire right_bridge1,right_bridge2;
    at8236_motor_driver #(.CLK_HZ(CLK_HZ),.PWM_HZ(PWM_HZ)) dr(.clk(clk),.rstn(rstn),.enable(control_enable),.command(pi_r),.in1(right_bridge1),.in2(right_bridge2),.pwm_abs(pwm_r));
    assign right_in1=RIGHT_BRIDGE_INVERT ? right_bridge2 : right_bridge1;
    assign right_in2=RIGHT_BRIDGE_INVERT ? right_bridge1 : right_bridge2;
    wire capability_req=cmd_valid && cmd_type==8'h40 && MOTION_CAPABILITIES!=0;
    wire status_req=capability_req || (cmd_valid && (cmd_type==8'h01 || cmd_type==8'h02 || cmd_type==8'h03 || cmd_type==8'h04 || cmd_type==8'h20 || cmd_type==8'h21 || cmd_type==8'h30)); wire [7:0] status_state=state_code;
    motion_status_tx #(.CLK_HZ(CLK_HZ)) st(.clk(clk),.rstn(rstn),.request(status_req),.capabilities_request(capability_req),.request_seq(cmd_seq),.state_code(status_state),.faults(faults),.left_count(left_count),.right_count(right_count),.left_speed(speed_l),.right_speed(speed_r),.left_pwm(pwm_l[15:0]),.right_pwm(pwm_r[15:0]),.command_age(command_age),.tx(uart_tx));
    always @(posedge clk or negedge rstn) begin
        if(!rstn) begin
            cpr_l<=CALIBRATED_DEFAULTS ? 1469 : 0;
            cpr_r<=CALIBRATED_DEFAULTS ? 1471 : 0;
            diam_l<=CALIBRATED_DEFAULTS ? 66 : 0;
            diam_r<=CALIBRATED_DEFAULTS ? 66 : 0;
            wheel_base<=CALIBRATED_DEFAULTS ? 121 : 0;
            max_speed<=CALIBRATED_DEFAULTS ? 400 : 0;
            counts_deg<=CALIBRATED_DEFAULTS ? 491 : 0;
            pi_limit<=PI_LIMIT_DEFAULT;ramp_limit<=RAMP_LIMIT_DEFAULT;
            params_valid<=CALIBRATED_DEFAULTS ? 7'h7f : 0;
            target_l<=0;target_r<=0;pending_v<=0;pending_omega<=0;twist_pending<=0;armed<=0;state_code<=0;faults<=0;command_age<=0;command_ttl<=250;rotate_start<=0; rotate_angle<=0; rotate_speed<=0;
        end
        else begin
            rotate_start<=0;
            if (twist_pending && control_enable) begin target_l<=twist_l; target_r<=twist_r; twist_pending<=0; state_code<=2; end
            if(ms_tick && command_age<65535) command_age<=command_age+1'b1;
            if(armed && (rotate_active || (target_l!=0)||(target_r!=0)) && command_age>command_ttl) begin faults[0]<=1; armed<=0; state_code<=3; end
            if(encoder_fault) begin faults[1]<=1; armed<=0; state_code<=3; end
            if(feedback_fault) begin faults[2]<=1; armed<=0; state_code<=3; end
            if(rotate_done) begin state_code<=1; target_l<=0; target_r<=0; end
            else if(rotate_active && control_enable) begin target_l<=rotate_l; target_r<=rotate_r; state_code<=2; end
            if(cmd_valid) begin
                if (cmd_ttl != 0) command_ttl <= cmd_ttl;
                case(cmd_type)
                    8'h01: ; // HELLO is read-only, not a state transition.
                    8'h02: if((&params_valid) && !faults && stop_n) begin armed<=1; state_code<=1; end
                    8'h03,8'h04: begin armed<=0; target_l<=0; target_r<=0; twist_pending<=0; rotate_start<=0; state_code<=faults!=0 ? 3 : 0; end
                    8'h05: if(armed && !faults) command_age<=0; // heartbeat, no motion restart
                    8'h10: if(armed&&!faults) begin pending_v<=payload[31:0]; pending_omega<={{16{payload[47]}},payload[47:32]}; twist_pending<=1; command_age<=0; end
                    8'h11: if(armed&&!faults) begin target_l<=payload[31:0]; target_r<=payload[63:32]; command_age<=0; state_code<=2; end
                    8'h12: if(control_enable && !rotate_active && !rotate_start) begin rotate_angle<=payload[31:0]; rotate_speed<=payload[47:32]; rotate_start<=1; twist_pending<=0; command_age<=0; state_code<=4; end
                    8'h21: if(!armed) begin faults<=0; state_code<=0; end
                    8'h30: begin
                        case(payload[7:0])
                            0: begin cpr_l<=payload[39:8]; params_valid[0]<=1; end
                            1: begin cpr_r<=payload[39:8]; params_valid[1]<=1; end
                            2: begin diam_l<=payload[39:8]; params_valid[2]<=1; end
                            3: begin diam_r<=payload[39:8]; params_valid[3]<=1; end
                            4: begin wheel_base<=payload[39:8]; params_valid[4]<=1; end
                            5: begin max_speed<=payload[39:8]; params_valid[5]<=1; end
                            6: begin counts_deg<=payload[39:8]; params_valid[6]<=1; end
                            7: ; // reserved for future PI gain profile
                            8: ; // reserved for future PI gain profile
                            9: pi_limit<=payload[23:8];
                            10: ramp_limit<=payload[23:8];
                            default: ;
                        endcase
                    end
                    default: ;
                endcase
            end
            // Fault wins over every command/pending target in this cycle.
            if(fault_now) begin
                armed<=0; target_l<=0; target_r<=0; twist_pending<=0; rotate_start<=0; state_code<=3;
                if(timeout_fault) faults[0]<=1;
                if(encoder_fault) faults[1]<=1;
                if(feedback_fault) faults[2]<=1;
            end
        end
    end
    assign led={rotate_active,(state_code==3),faults[2],faults[1],faults[0],armed,(state_code==2),rstn};
endmodule
`default_nettype wire
