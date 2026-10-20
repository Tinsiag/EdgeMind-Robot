`timescale 1ns/1ps
`default_nettype none
module a741_core #(parameter CLK_HZ=50000000,SENSOR_PINS_ENABLED=0,IMU_TEST=0,MOTION_LIDAR=0)(
    input wire clk,rst_n,imu_int,lidar_rx,
    inout wire imu_sda,imu_scl,
    inout wire tof_sda,tof_scl,tof_xshut,
    input wire left_a,left_b,right_a,right_b,
    output wire left_in1,left_in2,right_in1,right_in2,
    output wire lidar_control,
    input wire [7:0] eth_rx_data,input wire eth_rx_valid,eth_rx_last,eth_rx_bad,
    output wire eth_rx_ready,
    output wire [7:0] eth_tx_data,output wire eth_tx_valid,eth_tx_last,eth_tx_bad,
    input wire eth_tx_ready,
    input wire [7:0] video_data,input wire video_valid,video_last,
    input wire [15:0] video_length,output wire video_ready,
    input wire ddr_ready,frame_ready,camera_error,ddr_error,video_overflow,
    input wire [31:0] video_frames,
    output reg [895:0] snapshot,
    output wire [7:0] state,output wire [15:0] faults
);
    reg [31:0] divider;
    reg [3:0] period;
    wire ms_tick=divider==CLK_HZ/1000-1;
    wire tick=ms_tick && period==9;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin divider<=0;period<=0;end
        else if(ms_tick) begin divider<=0;period<=period==9 ? 0:period+1'b1;end
        else divider<=divider+1'b1;
    wire iv,gv,au,gu,tv,lv,lpv,imu_stationary;
    wire armed,calibrated,calibrating,rotating;
    wire signed [15:0] bias;
    wire signed [15:0] yaw,roll,pitch,gx,gy,gz;
    wire [31:0] now_ms,it,gt,isq,ie,tt,tsq,te,lt,lsq,le,ld;
    wire [15:0] tof,front,lside,rside;wire [7:0] tof_status;
    wire [375:0] lpacket;
    wire [31:0] imu_diagnostic;wire [95:0] imu_raw;wire [15:0] imu_temperature;
    a741_sensors #(.CLK_HZ(CLK_HZ),.AUX_ENABLED(IMU_TEST==0),.LIDAR_ENABLED(MOTION_LIDAR!=0 || IMU_TEST==0),
        .TOF_ENABLED(MOTION_LIDAR==0 && IMU_TEST==0),.ALLOW_MPU6500(IMU_TEST!=0 || MOTION_LIDAR!=0)) sensors(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.imu_int(imu_int),.imu_sda(imu_sda),.imu_scl(imu_scl),
        .calibrated(calibrated),.gyro_bias(bias),.imu_stationary(imu_stationary),.lidar_rx(lidar_rx),
        .tof_sda(tof_sda),.tof_scl(tof_scl),.tof_xshut(tof_xshut),
        .imu_valid(iv),.angle_update(au),.gyro_valid(gv),.gyro_update(gu),
        .yaw(yaw),.roll(roll),.pitch(pitch),.gx(gx),.gy(gy),.gz(gz),
        .imu_diagnostic(imu_diagnostic),.imu_raw(imu_raw),.imu_temperature(imu_temperature),
        .now_ms(now_ms),.imu_time(it),.gyro_time(gt),.imu_seq(isq),.imu_errors(ie),
        .tof_valid(tv),.tof_mm(tof),.tof_status(tof_status),.tof_time(tt),.tof_seq(tsq),.tof_errors(te),
        .lidar_valid(lv),.lidar_packet_valid(lpv),.lidar_packet(lpacket),.lidar_time(lt),
        .lidar_seq(lsq),.lidar_errors(le),.lidar_dropped(ld),.lidar_front(front),.lidar_left(lside),.lidar_right(rside));
    wire [7:0] crd,ctd;wire crv,crl,crb,crr,ctv,ctl,ctr;
    wire [15:0] ctlen;wire urx,utx;
    wire [31:0] rejected;
    a741_udp_control #(.CLK_HZ(CLK_HZ)) bridge(.clk(clk),.rst_n(rst_n),
        .rx_data(crd),.rx_valid(crv),.rx_last(crl),.rx_bad(crb),.rx_ready(crr),
        .tx_data(ctd),.tx_valid(ctv),.tx_last(ctl),.tx_length(ctlen),.tx_ready(ctr),
        .motion_uart_rx(urx),.motion_uart_tx(utx),.rejected(rejected));
    wire signed [31:0] lc,rc,lsp,rsp,tl,tr,relative;
    wire [15:0] lpwm,rpwm,command_age;
    wire [31:0] revision;wire [7:0] cal_result;
    a741_motion #(.CLK_HZ(CLK_HZ),.SENSOR_PINS_ENABLED(SENSOR_PINS_ENABLED),.IMU_TEST(IMU_TEST),.MOTION_LIDAR(MOTION_LIDAR)) motion(.clk(clk),.rst_n(rst_n),.uart_rx(urx),.uart_tx(utx),
        .lidar_control(lidar_control),
        .imu_diagnostic(imu_diagnostic),.imu_errors(ie),.imu_sequence(isq),.imu_raw(imu_raw),.imu_temperature(imu_temperature),
        .ms_tick(ms_tick),.tick(tick),.left_a(left_a),.left_b(left_b),.right_a(right_a),.right_b(right_b),
        .imu_valid(iv),.gyro_valid(gv),.imu_stationary(imu_stationary),.angle_update(au),.gyro_update(gu),.yaw(yaw),.gz(gz),
        .tof_valid(tv),.tof_mm(tof),.now_ms(now_ms),.left_in1(left_in1),.left_in2(left_in2),.right_in1(right_in1),.right_in2(right_in2),
        .armed(armed),.calibrated(calibrated),.calibrating(calibrating),.rotating(rotating),.faults(faults),
        .left_count(lc),.right_count(rc),.left_speed(lsp),.right_speed(rsp),.left_pwm(lpwm),.right_pwm(rpwm),
        .target_l(tl),.target_r(tr),.state_code(state),.config_revision(revision),
        .accumulated_yaw(relative),.gyro_bias(bias),.command_age(command_age),.calibration_result(cal_result));
    wire [7:0] td;wire tvld,tlast,trdy;wire [15:0] tlen;wire [31:0] dropped;
    reg [31:0] snapshot_seq;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin snapshot<=0;snapshot_seq<=0;end
        else if(ms_tick) begin
            snapshot_seq<=snapshot_seq+1'b1;
            snapshot<=0;
            snapshot[31:0]<=32'h31534d45;snapshot[47:32]<=1;snapshot[63:48]<=112;
            snapshot[95:64]<=snapshot_seq;snapshot[127:96]<=now_ms;snapshot[159:128]<=revision;
            snapshot[175:160]<={3'd0,video_overflow,ddr_error,camera_error,frame_ready,ddr_ready,rotating,calibrating,armed,calibrated,lv,tv,gv,iv};
            snapshot[183:176]<=state;snapshot[191:184]<=tof_status;snapshot[207:192]<=faults;
            snapshot[255:224]<=tl;snapshot[287:256]<=tr;
            snapshot[319:288]<=lsp;snapshot[351:320]<=rsp;
            snapshot[383:352]<=lc;snapshot[415:384]<=rc;
            snapshot[431:416]<=yaw;snapshot[447:432]<=gz;snapshot[463:448]<=tof;
            snapshot[479:464]<=front;snapshot[495:480]<=lside;snapshot[511:496]<=rside;
            snapshot[543:512]<=it;snapshot[575:544]<=tt;snapshot[607:576]<=lt;
            snapshot[639:608]<=ie;snapshot[671:640]<=te;snapshot[703:672]<=le;
            snapshot[735:704]<=dropped+ld;snapshot[767:736]<=gt;snapshot[783:768]<=bias;
            snapshot[791:784]<=cal_result;snapshot[799:792]<=0;
            snapshot[831:800]<=isq;snapshot[863:832]<=tsq;snapshot[895:864]<=lsq;
        end
    a741_telemetry telemetry(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.snapshot(snapshot),
        .lidar_update(lpv),.lidar_packet(lpacket),.lidar_time(lt),.lidar_seq(lsq),
        .data(td),.valid(tvld),.last(tlast),.length(tlen),.ready(trdy),.dropped(dropped));
    a741_router router(.clk(clk),.rst_n(rst_n),.eth_rx_data(eth_rx_data),.eth_rx_valid(eth_rx_valid),
        .eth_rx_last(eth_rx_last),.eth_rx_bad(eth_rx_bad),.eth_rx_ready(eth_rx_ready),
        .eth_tx_data(eth_tx_data),.eth_tx_valid(eth_tx_valid),.eth_tx_last(eth_tx_last),.eth_tx_bad(eth_tx_bad),.eth_tx_ready(eth_tx_ready),
        .control_rx_data(crd),.control_rx_valid(crv),.control_rx_last(crl),.control_rx_bad(crb),.control_rx_ready(crr),
        .control_tx_data(ctd),.control_tx_valid(ctv),.control_tx_last(ctl),.control_tx_length(ctlen),.control_tx_ready(ctr),
        .telemetry_data(td),.telemetry_valid(tvld),.telemetry_last(tlast),.telemetry_length(tlen),.telemetry_ready(trdy),
        .video_data(video_data),.video_valid(video_valid),.video_last(video_last),.video_length(video_length),.video_ready(video_ready));
endmodule
`default_nettype wire
