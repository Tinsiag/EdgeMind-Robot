`timescale 1ns/1ps
`default_nettype none
module a745_core #(parameter CLK_HZ=50000000,GEOMETRY_VERIFIED=0,LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1,
 RADIUS_MM=257,LIDAR_X=164,LIDAR_Y=0,TRACK_MM=234,FRONT_EXTENT=221,REAR_EXTENT=70,HALF_WIDTH=131,
 LEFT_CPR=1469,RIGHT_CPR=1471,LEFT_DIAMETER=66300,RIGHT_DIAMETER=66300,FUSION_CONFIG_CRC=0)(
 input wire clk,rst_n,button_start,imu_int,lidar_rx,
 input wire phy_ready,phy_error,input wire [7:0] mac_diagnostic,
 inout wire imu_sda,imu_scl,
 input wire left_a,left_b,right_a,right_b,
 output wire left_in1,left_in2,right_in1,right_in2,lidar_control,
 output wire [7:0] eth_tx_data,output wire eth_tx_valid,eth_tx_last,
 input wire eth_tx_ready,
 input wire ddr_ready,frame_ready,camera_error,ddr_error,video_overflow,
 input wire [31:0] video_frames,input wire [47:0] camera_diagnostic,
 output reg [895:0] snapshot,output wire [255:0] fusion_snapshot,
 output wire [7:0] state,output wire [15:0] faults
);
 localparam MS_DIV=CLK_HZ/1000;
 localparam DIV_BITS=$clog2(MS_DIV)>0 ? $clog2(MS_DIV):1;
 reg [DIV_BITS-1:0] divider;reg [3:0] period;
 wire ms_tick=divider==MS_DIV-1,tick=ms_tick && period==9;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin divider<=0;period<=0;end
  else if(ms_tick) begin divider<=0;period<=period==9 ? 0:period+1'b1;end
  else divider<=divider+1'b1;
 wire iv,gv,au,gu,stationary,tilt,lv,lpv,point,armed,calibrated,motor_enable,laser_enable;
 wire signed [15:0] bias,yaw,roll,pitch,gx,gy,gz;
 wire [31:0] now_ms,it,gt,isq,ie,lt,lsq,le,ld,imu_diagnostic;
 wire [95:0] raw;wire [15:0] temperature,front,left,right;wire [375:0] packet;
 wire [15:0] angle,distance;wire [7:0] confidence;
 a741_sensors #(.CLK_HZ(CLK_HZ),.LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE),
  .TOF_ENABLED(0),.ALLOW_MPU6500(1)) sensors(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),
  .imu_int(imu_int),.imu_sda(imu_sda),.imu_scl(imu_scl),.calibrated(calibrated),.gyro_bias(bias),
  .imu_stationary(stationary),.tilt_valid(tilt),.lidar_rx(lidar_rx),.tof_sda(),.tof_scl(),.tof_xshut(),
  .imu_valid(iv),.gyro_valid(gv),.angle_update(au),.gyro_update(gu),.yaw(yaw),.roll(roll),.pitch(pitch),
  .gx(gx),.gy(gy),.gz(gz),.imu_diagnostic(imu_diagnostic),.imu_raw(raw),.imu_temperature(temperature),
  .now_ms(now_ms),.imu_time(it),.gyro_time(gt),.imu_seq(isq),.imu_errors(ie),
  .lidar_valid(lv),.lidar_packet_valid(lpv),.lidar_packet(packet),.lidar_time(lt),.lidar_seq(lsq),
  .lidar_errors(le),.lidar_dropped(ld),.lidar_front(),.lidar_left(),.lidar_right(),
  .lidar_point(point),.lidar_angle(angle),.lidar_distance(distance),.lidar_confidence(confidence));
 wire cpu_alive,cpu_fault;wire [31:0] cpu_progress;
 a741_bare_cpu supervisor(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.armed(armed),
  .alive(cpu_alive),.fault(cpu_fault),.progress(cpu_progress));
 wire signed [1:0] ls,rs;wire li,ri,lto,rto;
 wire signed [31:0] lc,rc,delta_l,delta_r,speed_l,speed_r,target_l,target_r;
 wire [31:0] invalid_l,invalid_r;
 quadrature_decoder ql(.clk(clk),.rstn(rst_n),.a(left_a),.b(left_b),.invert(1'b0),.step(ls),.invalid(li));
 quadrature_decoder qr(.clk(clk),.rstn(rst_n),.a(right_a),.b(right_b),.invert(1'b1),.step(rs),.invalid(ri));
 encoder_counter #(.TIMEOUT_MS(1000)) el(.clk(clk),.rstn(rst_n),.step(ls),.invalid_step(li),.sample_tick(tick),
  .monitor_enable(motor_enable && target_l!=0),.count(lc),.delta(delta_l),.invalid_count(invalid_l),.feedback_timeout(lto));
 encoder_counter #(.TIMEOUT_MS(1000)) er(.clk(clk),.rstn(rst_n),.step(rs),.invalid_step(ri),.sample_tick(tick),
  .monitor_enable(motor_enable && target_r!=0),.count(rc),.delta(delta_r),.invalid_count(invalid_r),.feedback_timeout(rto));
 a741_speed sl(.clk(clk),.rst_n(rst_n),.tick(tick),.delta(delta_l),.cpr(32'(LEFT_CPR)),.diameter_um(32'(LEFT_DIAMETER)),.speed(speed_l));
 a741_speed sr(.clk(clk),.rst_n(rst_n),.tick(tick),.delta(delta_r),.cpr(32'(RIGHT_CPR)),.diameter_um(32'(RIGHT_DIAMETER)),.speed(speed_r));
 wire scan_valid,left_clear,right_clear;wire [15:0] rear;wire [7:0] scan_sequence;
 a745_navigation_scan #(.LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE)) scan_guard(
  .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.stream_valid(lv),.point_valid(point),.angle(angle),
  .distance(distance),.confidence(confidence),.scan_valid(scan_valid),.front(front),.left(left),.right(right),
  .rear(rear),.left_clear(left_clear),.right_clear(right_clear),.scan_sequence(scan_sequence));
 a745_autonomy #(.GEOMETRY_VERIFIED(GEOMETRY_VERIFIED)) autonomy(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(tick),
  .button_start(button_start),.imu_valid(iv),.gyro_valid(gv),.stationary(stationary),.gyro_update(gu),.tilt_valid(tilt),
  .raw_gz($signed(raw[95:80])),.roll(roll),.pitch(pitch),.yaw(yaw),.wheels_stationary(ls==0 && rs==0),
  .encoder_fault(lto || rto || invalid_l>64 || invalid_r>64),.cpu_alive(cpu_alive),.cpu_fault(cpu_fault),
  .lidar_valid(lv),.scan_valid(scan_valid),.front(front),.left(left),.right(right),.left_clear(left_clear),.right_clear(right_clear),
  .armed(armed),.calibrated(calibrated),.bias(bias),.lidar_enabled(laser_enable),.motor_enable(motor_enable),
  .state(state),.faults(faults),.target_l(target_l),.target_r(target_r));
 ld06_control #(.CLK_HZ(CLK_HZ)) laser(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.enabled(laser_enable),
  .update(ms_tick && laser_enable),.renew(ms_tick && laser_enable),.stop(!laser_enable),.duty_request(10'd400),.pwm(lidar_control),.status());
 wire signed [31:0] corrected_l,corrected_r,pi_l,pi_r,applied_l,applied_r;
 a741_motion_feedback feedback(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(motor_enable),.imu_valid(iv),
  .target_l(target_l),.target_r(target_r),.left_speed(speed_l),.right_speed(speed_r),.yaw(yaw),
  .corrected_l(corrected_l),.corrected_r(corrected_r),.heading_active(),.heading_error(),.speed_error());
 wire [9:0] speed_limit=state==2 ? (front>800 ? 10'd120:10'd60):10'd80;
 a741_pi #(.TARGET_LIMIT_ENABLED(1)) pl(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(motor_enable),
  .target(corrected_l),.measured(speed_l),.target_limit(speed_limit),.speed_step(16'd5),.pwm_step(16'd32),.limit(16'd512),.applied(applied_l),.command(pi_l));
 a741_pi #(.TARGET_LIMIT_ENABLED(1)) pr(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(motor_enable),
  .target(corrected_r),.measured(speed_r),.target_limit(speed_limit),.speed_step(16'd5),.pwm_step(16'd32),.limit(16'd512),.applied(applied_r),.command(pi_r));
 wire [15:0] pwm_l,pwm_r;
 motor_pwm_safe #(.CLK_HZ(CLK_HZ)) ml(.clk(clk),.rst_n(rst_n),.enable(motor_enable),.command(pi_l),.in1(left_in1),.in2(left_in2),.pwm_abs(pwm_l));
 motor_pwm_safe #(.CLK_HZ(CLK_HZ),.INVERT(1)) mr(.clk(clk),.rst_n(rst_n),.enable(motor_enable),.command(pi_r),.in1(right_in1),.in2(right_in2),.pwm_abs(pwm_r));
 reg [31:0] seq;wire [31:0] dropped;
 assign fusion_snapshot={48'd0,{5'd0,cpu_fault,cpu_alive,1'b0,cpu_progress},8'(scan_valid),32'd0,front,yaw,
  {31'd0,tilt},pitch,roll,8'(GEOMETRY_VERIFIED),faults[7:0],state,8'd1};
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin snapshot<=0;seq<=0;end
  else if(ms_tick) begin
   seq<=seq+1'b1;snapshot<=0;
   snapshot[31:0]<=32'h31534d45;snapshot[47:32]<=1;snapshot[63:48]<=112;
   snapshot[95:64]<=seq;snapshot[127:96]<=now_ms;snapshot[159:128]<=32'd74504;
   snapshot[175:160]<={1'b1,phy_error,phy_ready,video_overflow,ddr_error,camera_error,frame_ready,ddr_ready,
    1'b0,(state==1),armed,calibrated,lv,1'b0,gv,iv};
   snapshot[183:176]<=state;snapshot[191:184]<=255;snapshot[207:192]<=faults;
   snapshot[255:224]<=target_l;snapshot[287:256]<=target_r;snapshot[319:288]<=speed_l;snapshot[351:320]<=speed_r;
   snapshot[383:352]<=lc;snapshot[415:384]<=rc;snapshot[431:416]<=yaw;snapshot[447:432]<=gz;snapshot[463:448]<=65535;
   snapshot[479:464]<=front;snapshot[495:480]<=left;snapshot[511:496]<=right;
   snapshot[543:512]<=it;snapshot[575:544]<=camera_diagnostic[31:0];snapshot[607:576]<=lt;
   snapshot[639:608]<=ie;snapshot[671:640]<=video_frames;snapshot[703:672]<=le;snapshot[735:704]<=dropped+ld;
   snapshot[767:736]<=gt;snapshot[783:768]<=bias;snapshot[791:784]<=camera_diagnostic[47:40];
   snapshot[799:792]<=camera_diagnostic[39:32];snapshot[831:800]<=isq;snapshot[895:864]<=lsq;
   snapshot[847:832]<=rear;snapshot[855:848]<={6'd0,right_clear,left_clear};snapshot[863:856]<=scan_sequence;
  end
 a745_udp_tx #(.CLK_HZ(CLK_HZ)) telemetry(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.phy_ready(phy_ready),
  .snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.lidar_valid(lpv),.lidar_packet(packet),.lidar_seq(lsq),.lidar_time(lt),
  .data(eth_tx_data),.valid(eth_tx_valid),.last(eth_tx_last),.ready(eth_tx_ready),.dropped(dropped));
endmodule
`default_nettype wire
