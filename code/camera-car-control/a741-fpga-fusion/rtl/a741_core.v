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
    input wire [7:0] video_data,input wire video_valid,video_last,
    input wire [15:0] video_length,output wire video_ready,
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
    wire iv,gv,au,gu,tv,lv,lpv,imu_stationary;
    wire armed,calibrated,calibrating,rotating;
    wire signed [15:0] bias;
    wire signed [15:0] yaw,roll,pitch,gx,gy,gz;
    wire [31:0] now_ms,it,gt,isq,ie,tt,tsq,te,lt,lsq,le,ld;
    wire [15:0] tof,front,lside,rside;wire [7:0] tof_status;
    wire [375:0] lpacket;
    wire [31:0] imu_diagnostic;wire [95:0] imu_raw;wire [15:0] imu_temperature;
    wire lidar_point;wire [15:0] lidar_angle,lidar_distance;wire [7:0] lidar_confidence;
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
    wire signed [31:0] fl,fr,manual_l,manual_r,pose_x,pose_y;
    wire travel_tick,travel_valid,heading_positive;
    wire signed [31:0] left_travel,right_travel;
    wire signed [15:0] pose_heading;wire [7:0] nav_state,nav_fault,quality;wire [15:0] ffront;wire [31:0] map_revision;
    wire [7:0] mrd,mtd,mkind;wire mrv,mrl,mrb,mrr,mtv,mtl,mtr,mcommand,mwaiting;
    wire [15:0] mlen;wire [255:0] mpayload;
    reg map_owner,pending_control;reg [7:0] pending_kind;reg [255:0] pending_payload;
    wire control_is_nav=fkind>=8'h50 && fkind<=8'h59;
    wire deferred=pending_control && !mwaiting && !map_owner;
    wire acmd=mcommand || deferred || (fcommand && (!control_is_nav || !map_owner));
    wire [7:0] akind=mcommand ? mkind:deferred ? pending_kind:fkind;
    wire [255:0] apayload=mcommand ? mpayload:deferred ? pending_payload:fpayload;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin map_owner<=0;pending_control<=0;pending_kind<=0;pending_payload<=0;end
        else begin
            if(mcommand) map_owner<=1;
            if(freply_valid) map_owner<=0;
            if(fcommand && control_is_nav && map_owner) begin pending_control<=1;pending_kind<=fkind;pending_payload<=fpayload;end
            if(deferred) pending_control<=0;
        end
    a741_map_udp map_transport(.clk(clk),.rst_n(rst_n),.rx_data(mrd),.rx_valid(mrv),.rx_last(mrl),.rx_bad(mrb),.rx_ready(mrr),
        .tx_data(mtd),.tx_valid(mtv),.tx_last(mtl),.tx_length(mlen),.tx_ready(mtr),.command(mcommand),
        .command_ready(FUSION_ENABLED!=0 && bridge_state==0 && !fcommand && !pending_control),.kind(mkind),.payload(mpayload),
        .reply_done(freply_valid && map_owner),.reply(freply),.waiting(mwaiting));
    wire [39:0] mission_display;
    generate if(FUSION_ENABLED!=0) begin: fusion_enabled
        wire cpu_owns,cpu_alive,cpu_fault,cpu_reply_done,cpu_command,autonomy_owns,autonomy_stop,autonomy_reply_done;
        wire [7:0] cpu_kind;wire [255:0] cpu_payload,cpu_reply,autonomy_reply;
        wire [31:0] mission_progress;
        wire nav_busy,nav_arrived,nav_failed;
        reg mission_reply_owner,rejected_nav_reply,mission_session;
        wire rejected_nav=acmd && ((akind>=8'h50 && akind<=8'h57 && akind!=8'h56) || akind==8'h59) &&
            ((cpu_owns && akind<=8'h55) || mission_reply_owner || cpu_command);
        wire external_nav=acmd && akind!=8'h58 && !rejected_nav;
        a741_mission_cpu mission(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.armed(armed),
            .geometry_verified(GEOMETRY_VERIFIED!=0),.nav_busy(nav_busy),.nav_arrived(nav_arrived),.nav_failed(nav_failed),
            .host_command(acmd),.host_kind(akind),.host_payload(apayload),.host_reply_done(cpu_reply_done),.host_reply(cpu_reply),
            .nav_command(cpu_command),.nav_kind(cpu_kind),.nav_payload(cpu_payload),
            .nav_reply_done(autonomy_reply_done && mission_reply_owner),.nav_reply(autonomy_reply),
            .owns(cpu_owns),.alive(cpu_alive),.fault(cpu_fault),.progress(mission_progress));
        always @(posedge clk or negedge rst_n)
            if(!rst_n) begin mission_reply_owner<=0;rejected_nav_reply<=0;mission_session<=0;end
            else begin
                rejected_nav_reply<=rejected_nav;
                if(cpu_owns) mission_session<=1;
                else if(!armed || !autonomy_owns) mission_session<=0;
                if(cpu_command) mission_reply_owner<=1;
                else if(autonomy_reply_done) mission_reply_owner<=0;
            end
        assign fowns=autonomy_owns || cpu_owns;
        assign fstop=autonomy_stop || cpu_fault || (mission_session && !cpu_owns && autonomy_owns);
        assign freply_valid=cpu_reply_done || rejected_nav_reply || (autonomy_reply_done && !mission_reply_owner);
        assign freply=cpu_reply_done ? cpu_reply:rejected_nav_reply ? 256'd2:autonomy_reply;
        a741_autonomy #(.GEOMETRY_VERIFIED(GEOMETRY_VERIFIED),.RADIUS_MM(RADIUS_MM),.LIDAR_X(LIDAR_X),.LIDAR_Y(LIDAR_Y),
            .LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE),.TRACK_MM(TRACK_MM),.CONFIG_CRC(FUSION_CONFIG_CRC),
            .FRONT_EXTENT(FRONT_EXTENT),.REAR_EXTENT(REAR_EXTENT),.HALF_WIDTH(HALF_WIDTH)) autonomy(
            .clk(clk),.rst_n(rst_n),.tick(tick),.ms_tick(ms_tick),.imu_valid(iv && gv),
            .lidar_valid(lv && front!=65535 && lside!=65535 && rside!=65535),.calibrated(calibrated),
            .armed(armed),.link_alive(flink),.travel_tick(travel_tick),.travel_valid(travel_valid),.left_travel(left_travel),.right_travel(right_travel),
            .manual_left(manual_l),.manual_right(manual_r),.yaw(heading_positive ? yaw:-yaw),.motor_faults(faults),
            .lidar_point(lidar_point),.lidar_angle(lidar_angle),.lidar_distance(lidar_distance),.lidar_confidence(lidar_confidence),
              .lidar_front(front),.lidar_left(lside),.lidar_right(rside),
            .command(external_nav || cpu_command),.kind(cpu_command ? cpu_kind:akind),.payload(cpu_command ? cpu_payload:apayload),
            .reply_done(autonomy_reply_done),.reply(autonomy_reply),.drive_enabled(autonomy_owns),.force_stop(autonomy_stop),
            .mission_busy(nav_busy),.mission_arrived(nav_arrived),.mission_failed(nav_failed),
            .drive_left(fl),.drive_right(fr),.sensor_stop(fobstacle),.sensor_limit(flimit),.pose_x(pose_x),.pose_y(pose_y),.pose_heading(pose_heading),
            .nav_state(nav_state),.nav_fault(nav_fault),.localization_quality(quality),.front_distance(ffront),.map_revision(map_revision));
        assign mission_alive=autonomy_owns || (cpu_owns && cpu_alive);
        assign mission_display={5'd0,cpu_fault,cpu_alive,cpu_owns,mission_progress};
    end else begin
        assign freply_valid=0;assign freply=0;assign fowns=0;assign fstop=0;assign fobstacle=0;assign flimit=400;
        assign fl=0;assign fr=0;assign pose_x=0;assign pose_y=0;assign pose_heading=0;assign nav_state=0;assign nav_fault=0;assign quality=0;assign ffront=0;assign map_revision=0;
        assign mission_alive=0;
        assign mission_display=0;
    end endgenerate
    assign fusion_snapshot={48'd0,mission_display,quality,map_revision,ffront,pose_heading,pose_y,pose_x,8'(GEOMETRY_VERIFIED),nav_fault,nav_state,8'd1};
    wire mission_alive;
    a741_motion #(.CLK_HZ(CLK_HZ),.SENSOR_PINS_ENABLED(SENSOR_PINS_ENABLED),.IMU_TEST(IMU_TEST),.MOTION_LIDAR(MOTION_LIDAR),.FUSION_ENABLED(FUSION_ENABLED),.DIRECT_CONTROL(1)) motion(.clk(clk),.rst_n(rst_n),.uart_rx(1'b1),.uart_tx(),
        .direct_valid(command_valid),.direct_kind(command_kind),.direct_seq(command_seq),.direct_ttl(command_ttl),.direct_payload(command_payload),
        .direct_reply_valid(reply_valid),.direct_reply_kind(reply_kind),.direct_reply_seq(reply_seq),.direct_reply_length(reply_length),
        .direct_reply_payload(reply_payload),.direct_reply_ready(reply_ready),
        .fusion_owns(fowns),.fusion_stop(fstop),.obstacle_stop(fobstacle),.autonomy_alive(mission_alive),.fusion_left(fl),.fusion_right(fr),.obstacle_limit(flimit),
        .fusion_reply_valid(freply_valid && !map_owner),.fusion_reply(freply),.fusion_command(fcommand),.fusion_kind(fkind),.fusion_payload(fpayload),
        .command_link_alive(flink),.manual_left(manual_l),.manual_right(manual_r),
        .travel_tick(travel_tick),.travel_valid(travel_valid),.heading_positive(heading_positive),.left_travel(left_travel),.right_travel(right_travel),
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
    a741_router #(.MAP_ENABLED(FUSION_ENABLED)) router(.clk(clk),.rst_n(rst_n),.eth_rx_data(eth_rx_data),.eth_rx_valid(eth_rx_valid),
        .eth_rx_last(eth_rx_last),.eth_rx_bad(eth_rx_bad),.eth_rx_ready(eth_rx_ready),
        .eth_tx_data(eth_tx_data),.eth_tx_valid(eth_tx_valid),.eth_tx_last(eth_tx_last),.eth_tx_bad(eth_tx_bad),.eth_tx_ready(eth_tx_ready),
        .control_rx_data(crd),.control_rx_valid(crv),.control_rx_last(crl),.control_rx_bad(crb),.control_rx_ready(crr),
        .control_tx_data(ctd),.control_tx_valid(ctv),.control_tx_last(ctl),.control_tx_length(ctlen),.control_tx_ready(ctr),
        .telemetry_data(td),.telemetry_valid(tvld),.telemetry_last(tlast),.telemetry_length(tlen),.telemetry_ready(trdy),
        .video_data(video_data),.video_valid(video_valid),.video_last(video_last),.video_length(video_length),.video_ready(video_ready),
        .map_rx_data(mrd),.map_rx_valid(mrv),.map_rx_last(mrl),.map_rx_bad(mrb),.map_rx_ready(mrr),
        .map_tx_data(mtd),.map_tx_valid(mtv),.map_tx_last(mtl),.map_tx_length(mlen),.map_tx_ready(mtr));
endmodule
`default_nettype wire
