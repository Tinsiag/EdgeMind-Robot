`timescale 1ns/1ps
`default_nettype none
module a741_core #(parameter CLK_HZ=50000000,SENSOR_PINS_ENABLED=0,IMU_TEST=0,MOTION_LIDAR=0,PHY_DIAGNOSTICS=0,
    FUSION_ENABLED=0,GEOMETRY_VERIFIED=0,RADIUS_MM=0,LIDAR_X=0,LIDAR_Y=0,
    LIDAR_ZERO=27000,LIDAR_CLOCKWISE=1,TRACK_MM=234,FUSION_CONFIG_CRC=0,FRONT_EXTENT=220,REAR_EXTENT=70,HALF_WIDTH=131)(
    input wire clk,rst_n,imu_int,lidar_rx,
    input wire [7:0] mac_diagnostic,
    input wire phy_ready,phy_error,
    input wire [127:0] phy_diagnostic,
    inout wire imu_sda,imu_scl,
    inout wire tof_sda,tof_scl,tof_xshut,
    input wire left_a,left_b,right_a,right_b,
    output wire left_in1,left_in2,right_in1,right_in2,
    output wire lidar_control,
    input wire [7:0] eth_rx_data,input wire eth_rx_valid,eth_rx_last,eth_rx_bad,
    output wire eth_rx_ready,
    output wire [7:0] eth_tx_data,output wire eth_tx_valid,eth_tx_last,eth_tx_bad,
    input wire eth_tx_ready,
    input wire ddr_ready,frame_ready,camera_error,ddr_error,video_overflow,
    input wire [31:0] video_frames,
    output reg [895:0] snapshot,
    output wire [7:0] state,output wire [15:0] faults,
    output wire [255:0] fusion_snapshot
);
    reg [31:0] divider;
    reg [3:0] period;
    wire ms_tick=divider==CLK_HZ/1000-1;
    wire tick=ms_tick && period==9;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin divider<=0;period<=0;end
        else if(ms_tick) begin divider<=0;period<=period==9 ? 0:period+1'b1;end
        else divider<=divider+1'b1;
    wire iv,gv,au,gu,tv,lv,lpv,imu_stationary,tilt_valid;
    wire armed,calibrated,calibrating,rotating;
    wire signed [15:0] bias;
    wire signed [15:0] yaw,roll,pitch,gx,gy,gz;
    wire [31:0] now_ms,it,gt,isq,ie,tt,tsq,te,lt,lsq,le,ld;
    wire [15:0] tof,front,lside,rside;wire [7:0] tof_status;
    wire [375:0] lpacket;
    wire [31:0] imu_diagnostic;wire [95:0] imu_raw;wire [15:0] imu_temperature;
    wire lidar_point;wire [15:0] lidar_angle,lidar_distance;wire [7:0] lidar_confidence;
    a741_sensors #(.CLK_HZ(CLK_HZ),.LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE),.AUX_ENABLED(IMU_TEST==0),.LIDAR_ENABLED(MOTION_LIDAR!=0 || IMU_TEST==0),
        .TOF_ENABLED(MOTION_LIDAR==0 && IMU_TEST==0),.ALLOW_MPU6500(IMU_TEST!=0 || MOTION_LIDAR!=0)) sensors(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.imu_int(imu_int),.imu_sda(imu_sda),.imu_scl(imu_scl),
        .calibrated(calibrated),.gyro_bias(bias),.imu_stationary(imu_stationary),.tilt_valid(tilt_valid),.lidar_rx(lidar_rx),
        .tof_sda(tof_sda),.tof_scl(tof_scl),.tof_xshut(tof_xshut),
        .imu_valid(iv),.angle_update(au),.gyro_valid(gv),.gyro_update(gu),
        .yaw(yaw),.roll(roll),.pitch(pitch),.gx(gx),.gy(gy),.gz(gz),
        .imu_diagnostic(imu_diagnostic),.imu_raw(imu_raw),.imu_temperature(imu_temperature),
        .now_ms(now_ms),.imu_time(it),.gyro_time(gt),.imu_seq(isq),.imu_errors(ie),
        .tof_valid(tv),.tof_mm(tof),.tof_status(tof_status),.tof_time(tt),.tof_seq(tsq),.tof_errors(te),
        .lidar_valid(lv),.lidar_packet_valid(lpv),.lidar_packet(lpacket),.lidar_time(lt),
        .lidar_seq(lsq),.lidar_errors(le),.lidar_dropped(ld),.lidar_front(front),.lidar_left(lside),.lidar_right(rside),
        .lidar_point(lidar_point),.lidar_angle(lidar_angle),.lidar_distance(lidar_distance),.lidar_confidence(lidar_confidence));
    wire [7:0] crd,ctd;wire crv,crl,crb,crr,ctv,ctl,ctr;
    wire [15:0] ctlen;
    wire command_valid,reply_valid,reply_ready;
    wire [7:0] command_kind,command_seq,reply_kind,reply_seq,reply_length;
    wire [15:0] command_ttl;wire [255:0] command_payload,reply_payload;
    wire [31:0] rejected;
    wire [3:0] bridge_state;
    a741_udp_direct #(.CLK_HZ(CLK_HZ)) bridge(.clk(clk),.rst_n(rst_n),
        .rx_data(crd),.rx_valid(crv),.rx_last(crl),.rx_bad(crb),.rx_ready(crr),
        .tx_data(ctd),.tx_valid(ctv),.tx_last(ctl),.tx_length(ctlen),.tx_ready(ctr),
        .command(command_valid),.kind(command_kind),.seq(command_seq),.ttl(command_ttl),.payload(command_payload),
        .reply_valid(reply_valid),.reply_kind(reply_kind),.reply_seq(reply_seq),.reply_length(reply_length),
        .reply_payload(reply_payload),.reply_ready(reply_ready),.rejected(rejected),.diagnostic_state(bridge_state));
    wire signed [31:0] lc,rc,lsp,rsp,tl,tr,relative;
    wire [15:0] lpwm,rpwm,command_age;
    wire [31:0] revision;wire [7:0] cal_result;
    wire fcommand,fowns,fstop,fobstacle,freply_valid,flink;
    wire [7:0] fkind;wire [255:0] fpayload,freply;wire [9:0] flimit;
    wire signed [31:0] fl,fr,manual_l,manual_r,attitude_pair,reserved_status;
    wire signed [15:0] display_yaw;wire [7:0] avoid_state,avoid_fault,quality;wire [15:0] ffront;wire [31:0] reserved_revision;
    wire [39:0] cpu_display;
    generate if(FUSION_ENABLED!=0) begin: basic_enabled
        wire cpu_alive,cpu_fault;wire [31:0] cpu_progress;
        wire manual_stop,manual_scan_valid;wire [9:0] manual_limit;
        wire [15:0] manual_front,manual_rear,manual_nearest;
        wire avoidance_stop,avoidance_reply;
        a741_bare_cpu supervisor(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.armed(armed),
            .alive(cpu_alive),.fault(cpu_fault),.progress(cpu_progress));
        a741_lidar_guard #(.LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE),
            .ROTATION_CLEAR_MM(RADIUS_MM+(LIDAR_X<0 ? -LIDAR_X:LIDAR_X)+(LIDAR_Y<0 ? -LIDAR_Y:LIDAR_Y)+100)) manual_guard(
            .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.stream_valid(lv),.point_valid(lidar_point),
            .angle(lidar_angle),.distance(lidar_distance),.confidence(lidar_confidence),
            .requested_left(manual_l),.requested_right(manual_r),.stop(manual_stop),.limit(manual_limit),
            .scan_valid(manual_scan_valid),.front(manual_front),.rear(manual_rear),.nearest(manual_nearest));
        a741_avoidance #(.GEOMETRY_VERIFIED(GEOMETRY_VERIFIED),.CONFIG_CRC(FUSION_CONFIG_CRC)) avoidance(
            .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.armed(armed),.link_alive(flink),
            .motor_faults(faults),.imu_valid(iv),.tilt_valid(tilt_valid),.manual_left(manual_l),.manual_right(manual_r),
            .yaw(yaw),.roll(roll),.pitch(pitch),.lidar_valid(lv),
            .lidar_front(front),.lidar_left(lside),.lidar_right(rside),
            .manual_stop(manual_stop),.manual_limit(manual_limit),.manual_scan_valid(manual_scan_valid),
            .supervisor_alive(cpu_alive),.supervisor_fault(cpu_fault),.supervisor_uptime(cpu_progress),
            .command(fcommand),.kind(fkind),.payload(fpayload),.reply_done(freply_valid),.reply(freply),
            .drive_enabled(fowns),.force_stop(avoidance_stop),.drive_left(fl),.drive_right(fr),
            .sensor_stop(fobstacle),.sensor_limit(flimit),.state(avoid_state),.fault(avoid_fault),.front_distance(ffront));
        assign attitude_pair={pitch,roll};assign reserved_status={31'd0,tilt_valid};assign display_yaw=yaw;
        assign quality={7'd0,manual_scan_valid};assign reserved_revision=0;
        assign fstop=avoidance_stop || cpu_fault || (armed && !cpu_alive);
        assign cpu_display={5'd0,cpu_fault,cpu_alive,1'b0,cpu_progress};
    end else begin
        assign freply_valid=0;assign freply=0;assign fowns=0;assign fstop=0;assign fobstacle=0;assign flimit=400;
        assign fl=0;assign fr=0;assign attitude_pair=0;assign reserved_status=0;assign display_yaw=0;assign avoid_state=0;assign avoid_fault=0;assign quality=0;assign ffront=0;assign reserved_revision=0;
        assign cpu_display=0;
    end endgenerate
    assign fusion_snapshot={48'd0,cpu_display,quality,reserved_revision,ffront,display_yaw,reserved_status,attitude_pair,8'(GEOMETRY_VERIFIED),avoid_fault,avoid_state,8'd1};
    a741_motion #(.CLK_HZ(CLK_HZ),.SENSOR_PINS_ENABLED(SENSOR_PINS_ENABLED),.IMU_TEST(IMU_TEST),.MOTION_LIDAR(MOTION_LIDAR),.FUSION_ENABLED(FUSION_ENABLED)) motion(.clk(clk),.rst_n(rst_n),
        .direct_valid(command_valid),.direct_kind(command_kind),.direct_seq(command_seq),.direct_ttl(command_ttl),.direct_payload(command_payload),
        .direct_reply_valid(reply_valid),.direct_reply_kind(reply_kind),.direct_reply_seq(reply_seq),.direct_reply_length(reply_length),
        .direct_reply_payload(reply_payload),.direct_reply_ready(reply_ready),
        .fusion_owns(fowns),.fusion_stop(fstop),.obstacle_stop(fobstacle),.fusion_left(fl),.fusion_right(fr),.obstacle_limit(flimit),
        .fusion_reply_valid(freply_valid),.fusion_reply(freply),.fusion_command(fcommand),.fusion_kind(fkind),.fusion_payload(fpayload),
        .command_link_alive(flink),.manual_left(manual_l),.manual_right(manual_r),
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
    wire [255:0] phy_snapshot={phy_diagnostic,now_ms,snapshot_seq,16'd32,16'd1,32'h31504d45};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin snapshot<=0;snapshot_seq<=0;end
        else if(ms_tick) begin
            snapshot_seq<=snapshot_seq+1'b1;
            snapshot<=0;
            snapshot[31:0]<=32'h31534d45;snapshot[47:32]<=1;snapshot[63:48]<=112;
            snapshot[95:64]<=snapshot_seq;snapshot[127:96]<=now_ms;snapshot[159:128]<=revision;
            snapshot[175:160]<={1'b1,phy_error,phy_ready,video_overflow,ddr_error,camera_error,frame_ready,ddr_ready,rotating,calibrating,armed,calibrated,lv,tv,gv,iv};
            snapshot[183:176]<=state;snapshot[191:184]<=tof_status;snapshot[207:192]<=faults;
            snapshot[223:208]<={rejected[3:0],bridge_state,mac_diagnostic};
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
    a741_telemetry #(.PHY_DIAGNOSTICS(PHY_DIAGNOSTICS),.FUSION_ENABLED(FUSION_ENABLED)) telemetry(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.snapshot(snapshot),
        .phy_snapshot(phy_snapshot),
        .fusion_snapshot(fusion_snapshot),
        .lidar_update(lpv),.lidar_packet(lpacket),.lidar_time(lt),.lidar_seq(lsq),
        .data(td),.valid(tvld),.last(tlast),.length(tlen),.ready(trdy),.dropped(dropped));
    a741_router router(.clk(clk),.rst_n(rst_n),.eth_rx_data(eth_rx_data),.eth_rx_valid(eth_rx_valid),
        .eth_rx_last(eth_rx_last),.eth_rx_bad(eth_rx_bad),.eth_rx_ready(eth_rx_ready),
        .eth_tx_data(eth_tx_data),.eth_tx_valid(eth_tx_valid),.eth_tx_last(eth_tx_last),.eth_tx_bad(eth_tx_bad),.eth_tx_ready(eth_tx_ready),
        .control_rx_data(crd),.control_rx_valid(crv),.control_rx_last(crl),.control_rx_bad(crb),.control_rx_ready(crr),
        .control_tx_data(ctd),.control_tx_valid(ctv),.control_tx_last(ctl),.control_tx_length(ctlen),.control_tx_ready(ctr),
        .telemetry_data(td),.telemetry_valid(tvld),.telemetry_last(tlast),.telemetry_length(tlen),.telemetry_ready(trdy));
endmodule
`default_nettype wire
