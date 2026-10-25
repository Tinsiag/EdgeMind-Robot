`timescale 1ns/1ps
`default_nettype none
module a741_motion #(parameter CLK_HZ=50000000,SENSOR_PINS_ENABLED=0,IMU_TEST=0,MOTION_LIDAR=0)(
    input wire [31:0] imu_diagnostic,imu_errors,imu_sequence,
    input wire [95:0] imu_raw,input wire [15:0] imu_temperature,
    input wire clk,rst_n,uart_rx,ms_tick,tick,
    input wire left_a,left_b,right_a,right_b,
    input wire imu_valid,gyro_valid,angle_update,gyro_update,
    input wire imu_stationary,
    input wire signed [15:0] yaw,gz,
    input wire tof_valid,input wire [15:0] tof_mm,
    input wire [31:0] now_ms,
    output wire uart_tx,left_in1,left_in2,right_in1,right_in2,
    output wire lidar_control,
    output reg armed,calibrated,calibrating,rotating,
    output reg [15:0] faults,
    output wire signed [31:0] left_count,right_count,left_speed,right_speed,
    output wire [15:0] left_pwm,right_pwm,
    output reg signed [31:0] target_l,target_r,
    output wire [7:0] state_code,
    output reg [31:0] config_revision,
    output reg signed [31:0] accumulated_yaw,
    output reg signed [15:0] gyro_bias,
    output reg [15:0] command_age,
    output reg [7:0] calibration_result
);
    wire [7:0] byte_data;wire byte_valid,uart_error;
    uart_rx #(.CLK_HZ(CLK_HZ)) receiver(.clk(clk),.rstn(rst_n),.rx(uart_rx),.data(byte_data),.valid(byte_valid),.framing_error(uart_error));
    wire cv,crc_error,length_error;wire [7:0] kind,seq;wire [15:0] ttl;wire [255:0] payload;
    a741_protocol protocol(.clk(clk),.rstn(rst_n),.rx_data(byte_data),.rx_valid(byte_valid),.cmd_valid(cv),
        .cmd_type(kind),.cmd_seq(seq),.cmd_ttl_ms(ttl),.cmd_payload(payload),.crc_error(crc_error),.length_error(length_error));
    reg [31:0] cfg[0:11];reg [11:0] configured;
    wire config_ok=&configured;
    // Static IMU testing does not require a fabricated mechanical track.
    wire calibration_config_ok=(IMU_TEST!=0 || MOTION_LIDAR!=0) ? (&configured[11:5] && &configured[3:0]):config_ok;
    wire signed [1:0] ls,rs;wire li,ri,lto,rto;wire [31:0] ld,rd,lic,ric;
    quadrature_decoder ql(.clk(clk),.rstn(rst_n),.a(left_a),.b(left_b),.invert(1'b0),.step(ls),.invalid(li));
    quadrature_decoder qr(.clk(clk),.rstn(rst_n),.a(right_a),.b(right_b),.invert(1'b1),.step(rs),.invalid(ri));
    wire active=IMU_TEST==0 && armed && faults==0;
    encoder_counter el(.clk(clk),.rstn(rst_n),.step(ls),.invalid_step(li),.sample_tick(tick),
        .monitor_enable(active && target_l!=0),.count(left_count),.delta(ld),.invalid_count(lic),.feedback_timeout(lto));
    encoder_counter er(.clk(clk),.rstn(rst_n),.step(rs),.invalid_step(ri),.sample_tick(tick),
        .monitor_enable(active && target_r!=0),.count(right_count),.delta(rd),.invalid_count(ric),.feedback_timeout(rto));
    a741_speed sl(.clk(clk),.rst_n(rst_n),.tick(tick),.delta($signed(ld)),.cpr(cfg[0]),.diameter_um(cfg[2]),.speed(left_speed));
    a741_speed sr(.clk(clk),.rst_n(rst_n),.tick(tick),.delta($signed(rd)),.cpr(cfg[1]),.diameter_um(cfg[3]),.speed(right_speed));
    wire stop_cmd=cv && (kind==3 || kind==4);
    reg [15:0] effective_ttl;
    reg imu_required,heading_hold;
    reg signed [15:0] heading_origin,previous_yaw;
    reg signed [31:0] turn_target;
    reg [15:0] turn_speed,quiet_ms,calibration_age;
    reg turn_braking;
    reg [6:0] bias_count;reg signed [31:0] bias_sum;
    reg [31:0] cal_start_ms;
    wire [31:0] clearance=tof_mm>cfg[8] ? tof_mm-cfg[8]:0;
    wire moving=(target_l!=0 || target_r!=0 || rotating || applied_l!=0 || applied_r!=0 || pi_l!=0 || pi_r!=0);
    wire forward=!rotating && ($signed(target_l)+$signed(target_r)>0 ||
        $signed(desired_l)+$signed(desired_r)>0 || $signed(applied_l)+$signed(applied_r)>0);
    wire feedback_fault=(target_l!=0 && lto)||(target_r!=0 && rto);
    wire imu_fault=(imu_required || moving) && (!imu_valid || !gyro_valid);
    wire tof_fault=MOTION_LIDAR==0 && forward && (!tof_valid || clearance<=250);
    // ARM itself expires, even before the first speed command arrives.
    wire timeout_fault=armed && command_age>=effective_ttl;
    wire hard_fault=active && (feedback_fault || imu_fault || tof_fault || timeout_fault);
    wire enable=active && !stop_cmd && !hard_fault;
    reg signed [10:0] desired_l,desired_r;
    reg signed [31:0] req_l,req_r;
    reg signed [15:0] delta_yaw;
    wire targets_valid,targets_braking;
    wire signed [31:0] next_target_l,next_target_r;
    wire replace_targets=cv && (kind==8'h11 || kind==8'h45 || kind==8'h42);
    a741_targets targets(.clk(clk),.rst_n(rst_n),.enable(enable),.tick(tick),.cancel(replace_targets),
        .rotating(rotating),.turn_braking(turn_braking),.heading_hold(heading_hold && imu_valid),
        .heading_positive(cfg[7]==1),.desired_l(desired_l),.desired_r(desired_r),
        .yaw(yaw),.heading_origin(heading_origin),.gz(gz),.gyro_bias(gyro_bias),
        .turn_target(turn_target),.accumulated_yaw(accumulated_yaw),.left_speed(left_speed),.right_speed(right_speed),
        .max_speed(cfg[5][8:0]),.turn_speed(turn_speed[8:0]),.speed_step(cfg[10][5:0]),
        .tof_valid(MOTION_LIDAR!=0 || tof_valid),.clearance(MOTION_LIDAR!=0 ? 32'd1000:clearance),.valid(targets_valid),.braking(targets_braking),
        .target_l(next_target_l),.target_r(next_target_r));
    wire signed [31:0] pi_l,pi_r,applied_l,applied_r;
    a741_pi pl(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(enable),.target(target_l),.measured(left_speed),
        .speed_step(cfg[10][15:0]),.pwm_step(cfg[11][15:0]),.limit(cfg[9][15:0]),.applied(applied_l),.command(pi_l));
    a741_pi pr(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(enable),.target(target_r),.measured(right_speed),
        .speed_step(cfg[10][15:0]),.pwm_step(cfg[11][15:0]),.limit(cfg[9][15:0]),.applied(applied_r),.command(pi_r));
    motor_pwm_safe #(.CLK_HZ(CLK_HZ)) ml(.clk(clk),.rst_n(rst_n),.enable(enable),.command(pi_l),.in1(left_in1),.in2(left_in2),.pwm_abs(left_pwm));
    motor_pwm_safe #(.CLK_HZ(CLK_HZ),.INVERT(1)) mr(.clk(clk),.rst_n(rst_n),.enable(enable),.command(pi_r),.in1(right_in1),.in2(right_in2),.pwm_abs(right_pwm));
    assign state_code=faults!=0 ? 3 : rotating ? 4 : armed ? (moving || pi_l!=0 || pi_r!=0 ? 2:1):0;
    reg reply_request;reg [7:0] reply_kind,reply_seq,reply_length;reg [255:0] reply_payload;wire reply_ready;
    reg request_pending;reg [7:0] saved_kind,saved_seq;reg [31:0] saved_key;
    vision_packet_tx #(.CLK_HZ(CLK_HZ)) responses(.clk(clk),.rst_n(rst_n),.request(reply_request),.kind(reply_kind),
        .seq(reply_seq),.length(reply_length),.payload(reply_payload),.ready(reply_ready),.tx(uart_tx));
    integer i;
    reg value_ok;reg [7:0] key;reg [31:0] value;
    reg [9:0] lidar_duty;
    wire [31:0] lidar_status;
    wire lidar_renew=cv && kind==8'h05;
    wire lidar_update=cv && kind==8'h46 && MOTION_LIDAR!=0 &&
        (payload[15:0]==0 || (payload[15:0]>=200 && payload[15:0]<=600));
    wire lidar_stop=cv && kind==8'h04;
    ld06_control #(.CLK_HZ(CLK_HZ)) lidar_motor(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),
        .enabled(MOTION_LIDAR!=0),.update(lidar_update),.renew(lidar_renew),.stop(lidar_stop),.duty_request(lidar_duty),
        .pwm(lidar_control),.status(lidar_status));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            for(i=0;i<12;i=i+1) cfg[i]<=0;
            configured<=0;armed<=0;faults<=0;calibrated<=0;calibrating<=0;rotating<=0;imu_required<=0;
            target_l<=0;target_r<=0;desired_l<=0;desired_r<=0;heading_hold<=0;heading_origin<=0;previous_yaw<=0;
            turn_target<=0;turn_speed<=0;turn_braking<=0;quiet_ms<=0;accumulated_yaw<=0;command_age<=0;effective_ttl<=250;
            bias_count<=0;bias_sum<=0;gyro_bias<=0;calibration_age<=0;cal_start_ms<=0;calibration_result<=0;config_revision<=0;
            reply_request<=0;reply_kind<=0;reply_seq<=0;reply_length<=0;reply_payload<=0;
            request_pending<=0;saved_kind<=0;saved_seq<=0;saved_key<=0;lidar_duty<=0;
        end else begin
            reply_request<=0;
            if(!imu_valid || !gyro_valid) calibrated<=0;
            if(ms_tick) begin
                if(command_age!=65535) command_age<=command_age+1'b1;
                if(calibrating && calibration_age!=65535) calibration_age<=calibration_age+1'b1;
                if(rotating && turn_braking && target_l==0 && target_r==0 && left_speed<20 && left_speed>-20 && right_speed<20 && right_speed>-20 &&
                    ($signed({{16{gz[15]}},gz})-$signed({{16{gyro_bias[15]}},gyro_bias}))<33 &&
                    ($signed({{16{gz[15]}},gz})-$signed({{16{gyro_bias[15]}},gyro_bias}))> -33) begin
                    if(quiet_ms<200) quiet_ms<=quiet_ms+1'b1;
                    else begin
                        rotating<=0;
                        if(turn_target-accumulated_yaw>910 || turn_target-accumulated_yaw< -910) faults[9]<=1;
                    end
                end else quiet_ms<=0;
            end
            if(calibrating && gyro_update) begin
                if(!imu_valid || !imu_stationary || gz>82 || gz < -82 || ls!=0 || rs!=0) begin calibrating<=0;calibration_result<=2;end
                else if(bias_count==63) begin
                    gyro_bias<=($signed(bias_sum)+$signed(gz))/64;calibrated<=1;calibrating<=0;calibration_result<=1;
                end else begin bias_sum<=bias_sum+$signed(gz);bias_count<=bias_count+1'b1;end
            end
            if(calibrating && angle_update) begin
                delta_yaw=yaw-heading_origin;
                if(delta_yaw>364 || delta_yaw< -364) begin
                    calibrated<=0;calibrating<=0;calibration_result<=2;
                end
            end
            if(calibrating && (calibration_age>=12000 || !imu_valid || !gyro_valid || ls!=0 || rs!=0)) begin
                calibrated<=0;calibrating<=0;calibration_result<=3;
            end
            if(rotating && angle_update) begin
                delta_yaw=yaw-previous_yaw;
                accumulated_yaw<=accumulated_yaw+(cfg[7]==1 ? $signed(delta_yaw):-$signed(delta_yaw));previous_yaw<=yaw;
            end
            if(targets_valid && enable && !replace_targets) begin
                target_l<=next_target_l;target_r<=next_target_r;
                if(rotating && targets_braking) turn_braking<=1;
            end
            // Reply fields are captured one cycle after command state updates.
            if(request_pending && reply_ready && !reply_request) begin
                request_pending<=0;reply_request<=1;reply_kind<=8'h80;reply_seq<=saved_seq;reply_length<=25;reply_payload<=0;
                reply_payload[7:0]<=state_code;reply_payload[23:8]<=faults;
                reply_payload[55:24]<=left_count;reply_payload[87:56]<=right_count;
                reply_payload[119:88]<=left_speed;reply_payload[151:120]<=right_speed;
                reply_payload[167:152]<=left_pwm;reply_payload[183:168]<=right_pwm;reply_payload[199:184]<=command_age;
                if(saved_kind==8'h40) begin
                    reply_kind<=8'hc0;reply_length<=8;
                    reply_payload<={192'd0,16'd400,(MOTION_LIDAR!=0 ? 16'h0351:IMU_TEST!=0 ? 16'h00d1:SENSOR_PINS_ENABLED!=0 ? 16'h0031:16'h0011),32'h314d5645};
                end
                else if(saved_kind==8'h41 || saved_kind==8'h43) begin
                    reply_kind<=8'hc1;reply_length<=32;
                    reply_payload<=0;
                    reply_payload[7:0]<=1;
                    reply_payload[15:8]<={4'd0,calibrating,calibrated,rotating,armed};
                    reply_payload[23:16]<={5'd0,tof_valid,gyro_valid,imu_valid};
                    reply_payload[31:24]<=calibration_result;
                    reply_payload[47:32]<=yaw;reply_payload[63:48]<=gz;
                    reply_payload[79:64]<=tof_mm;reply_payload[95:80]<=faults;
                    reply_payload[127:96]<=now_ms;reply_payload[159:128]<=accumulated_yaw;
                    reply_payload[191:160]<=config_revision;reply_payload[207:192]<=gyro_bias;
                end else if(saved_kind==8'h44) begin
                    reply_kind<=8'hc4;reply_length<=12;reply_payload<=0;
                    reply_payload[31:0]<=saved_key;
                    reply_payload[63:32]<=saved_key<12 ? cfg[saved_key[3:0]] :
                        saved_key==12 ? 32'd6050:saved_key==13 ? 32'd2:
                        saved_key==14 ? imu_diagnostic:saved_key==15 ? imu_errors:saved_key==16 ? imu_sequence:
                        saved_key==17 ? imu_raw[31:0]:saved_key==18 ? imu_raw[63:32]:saved_key==19 ? imu_raw[95:64]:
                        saved_key==20 ? {16'd0,imu_temperature}:saved_key==21 ? lidar_status:32'hffffffff;
                    reply_payload[95:64]<=config_revision;
                end
            end
            if(cv) begin
                if(ttl!=0) effective_ttl<=ttl>1000 ? 1000 : ttl<50 ? 50:ttl;
                if(kind!=8'h05 && kind!=8'h11 && kind!=8'h45) begin
                    request_pending<=1;saved_kind<=kind;saved_seq<=seq;saved_key<=payload[31:0];
                end
                case(kind)
                    8'h02: if(IMU_TEST==0 && calibration_config_ok && calibrated && !calibrating && imu_valid && gyro_valid && faults==0) begin armed<=1;command_age<=0;end
                    8'h03,8'h04: begin armed<=0;rotating<=0;heading_hold<=0;imu_required<=0;target_l<=0;target_r<=0;desired_l<=0;desired_r<=0;
                        calibrating<=0;if(calibrating) calibration_result<=4;
                    end
                    8'h05: if(armed) command_age<=0;
                    8'h46: if(MOTION_LIDAR!=0 && (payload[15:0]==0 || (payload[15:0]>=200 && payload[15:0]<=600))) lidar_duty<=payload[9:0];
                    8'h11,8'h45: if(active && !rotating) begin
                        req_l=$signed(payload[31:0]);req_r=$signed(payload[63:32]);
                        // Reject out-of-range commands rather than overflow signed arithmetic.
                        if(req_l>400 || req_l< -400 || req_r>400 || req_r< -400) begin req_l=0;req_r=0;end
                        desired_l<=req_l;desired_r<=req_r;
                        heading_hold<=kind==8'h45 && req_l==req_r && req_l!=0;
                        // Every new straight/arc command starts from the current
                        // IMU heading; never reuse the previous task's origin.
                        heading_origin<=yaw;
                        imu_required<=req_l!=0 || req_r!=0;command_age<=0;
                    end
                    8'h21: if(!armed && !moving && left_speed<20 && left_speed>-20 && right_speed<20 && right_speed>-20) faults<=0;
                    8'h30: if(!armed && !calibrating) begin
                        key=payload[7:0];value=payload[39:8];value_ok=0;
                        case(key)
                            0,1:value_ok=value>=100 && value<=20000;
                            2,3:value_ok=value>=10000 && value<=200000;
                            4:value_ok=value>=50000 && value<=1000000;
                            5:value_ok=value>=40 && value<=400;
                            6:value_ok=value!=0;
                            7:value_ok=value==1 || value==32'hffffffff;
                            8:value_ok=value<=1000;
                            9:value_ok=value<=512;
                            10:value_ok=value>=1 && value<=50;
                            11:value_ok=value>=1 && value<=128;
                            default:value_ok=0;
                        endcase
                        if(value_ok) begin cfg[key[3:0]]<=value;configured[key[3:0]]<=1;calibrated<=0;end
                        if(key==6 && value_ok) config_revision<=value;
                    end
                    8'h42: if(active && !moving && desired_l==0 && desired_r==0 &&
                        left_speed<20 && left_speed> -20 && right_speed<20 && right_speed> -20 &&
                        calibrated && imu_valid && gyro_valid && $signed(payload[31:0])!=0 &&
                        $signed(payload[31:0])<=65536 && $signed(payload[31:0])>=-65536 && payload[47:32]>=40 && payload[47:32]<=cfg[5]) begin
                        rotating<=1;imu_required<=1;turn_target<=payload[31:0];turn_speed<=payload[47:32];
                        accumulated_yaw<=0;previous_yaw<=yaw;command_age<=0;quiet_ms<=0;turn_braking<=0;
                        heading_hold<=0;desired_l<=0;desired_r<=0;
                    end
                    8'h43: if(!armed && calibration_config_ok && imu_valid && gyro_valid && imu_stationary && left_speed==0 && right_speed==0) begin
                        calibrated<=0;calibrating<=1;bias_count<=0;bias_sum<=0;calibration_age<=0;cal_start_ms<=now_ms;calibration_result<=0;heading_origin<=yaw;
                    end
                    default:;
                endcase
            end
            if(hard_fault || faults[9]) begin
                armed<=0;rotating<=0;heading_hold<=0;target_l<=0;target_r<=0;desired_l<=0;desired_r<=0;
                if(timeout_fault) faults[0]<=1;
                if(feedback_fault) faults[2]<=1;
                if(imu_fault) faults[4]<=1;
                if(tof_fault) faults[5]<=1;
            end
        end
endmodule
`default_nettype wire
