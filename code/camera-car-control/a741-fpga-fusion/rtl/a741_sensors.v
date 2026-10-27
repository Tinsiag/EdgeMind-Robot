`timescale 1ns/1ps
`default_nettype none
module a741_sensors #(parameter LIDAR_ZERO=0,LIDAR_CLOCKWISE=0,CLK_HZ=50000000,AUX_ENABLED=1,ALLOW_MPU6500=0,
    LIDAR_ENABLED=AUX_ENABLED,TOF_ENABLED=AUX_ENABLED)(
    input wire clk,rst_n,ms_tick,lidar_rx,imu_int,calibrated,
    input wire signed [15:0] gyro_bias,
    inout wire imu_sda,imu_scl,
    inout wire tof_sda,tof_scl,tof_xshut,
    output wire imu_valid,angle_update,gyro_valid,gyro_update,imu_stationary,tilt_valid,
    output wire signed [15:0] yaw,roll,pitch,gx,gy,gz,
    output wire [31:0] now_ms,imu_time,gyro_time,imu_seq,imu_errors,imu_diagnostic,
    output wire [95:0] imu_raw,output wire [15:0] imu_temperature,
    output wire tof_valid,output wire [15:0] tof_mm,
    output wire [7:0] tof_status,output wire [31:0] tof_time,tof_seq,tof_errors,
    output wire lidar_valid,lidar_packet_valid,output wire [375:0] lidar_packet,
    output wire [31:0] lidar_time,lidar_seq,lidar_errors,lidar_dropped,
    output wire [15:0] lidar_front,lidar_left,lidar_right,
    output wire lidar_point,output wire [15:0] lidar_angle,lidar_distance,output wire [7:0] lidar_confidence
);
    wire [7:0] lb;wire lv,le;
    uart_rx #(.CLK_HZ(CLK_HZ),.BAUD(230400)) lu(.clk(clk),.rstn(rst_n),.rx(lidar_rx),.data(lb),.valid(lv),.framing_error(le));
    reg [31:0] time_ms;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) time_ms<=0;else if(ms_tick) time_ms<=time_ms+1'b1;
    assign now_ms=time_ms;
    wire istart,iread,ibusy,idone,ierror,sample_update,sample_valid;
    wire [6:0] iaddress;wire [7:0] ireg;wire [3:0] icount;
    wire [111:0] iwrite,iread_data;
    wire signed [15:0] ax,ay,az,raw_gz;
    wire imu_ready;wire [7:0] imu_fault,who;
    assign imu_diagnostic={5'd0,sample_valid,imu_stationary,imu_ready,imu_fault,who,1'b0,iaddress};
    assign imu_raw={raw_gz,gy,gx,az,ay,ax};
    a741_imu_i2c #(.CLK_HZ(CLK_HZ),.I2C_HZ(100000)) imu_bus(.clk(clk),.rst_n(rst_n),
        .start(istart),.read(iread),.address(iaddress),.reg_addr(ireg),.byte_count(icount),
        .write_data(iwrite),.read_data(iread_data),.busy(ibusy),.done(idone),.error(ierror),
        .sda(imu_sda),.scl(imu_scl));
    mpu6050_driver #(.ALLOW_MPU6500(ALLOW_MPU6500)) imu(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.now_ms(now_ms),
        .start(istart),.read(iread),.address(iaddress),.reg_addr(ireg),.byte_count(icount),
        .write_data(iwrite),.read_data(iread_data),.busy(ibusy),.done(idone),.error(ierror),
        .sample_update(sample_update),.valid(sample_valid),.ready(imu_ready),.fault(imu_fault),.who_am_i(who),
        .ax(ax),.ay(ay),.az(az),.gx(gx),.gy(gy),.gz(raw_gz),.temperature(imu_temperature),
        .sample_time(imu_time),.sequence_id(imu_seq),.errors(imu_errors));
    mpu6050_heading heading(.clk(clk),.rst_n(rst_n),.sample_update(sample_update),.sample_valid(sample_valid),
        .raw_gz(raw_gz),.ax(ax),.ay(ay),.az(az),.sample_time(imu_time),.calibrated(calibrated),.gyro_bias(gyro_bias),
        .yaw(yaw),.gz(gz),.angle_update(angle_update),.gyro_update(gyro_update),.valid(imu_valid),.stationary(imu_stationary));
    assign gyro_valid=sample_valid;
    assign gyro_time=imu_time;
    a741_attitude inclination(.clk(clk),.rst_n(rst_n),.sample_update(sample_update),.sample_valid(sample_valid),
        .ax(ax),.ay(ay),.az(az),.roll(roll),.pitch(pitch),.valid(tilt_valid),.done());
    ld06_parser #(.LIDAR_ZERO(LIDAR_ZERO),.LIDAR_CLOCKWISE(LIDAR_CLOCKWISE)) lidar(.clk(clk),.rst_n(rst_n && LIDAR_ENABLED!=0),.ms_tick(ms_tick),.byte_valid(lv),.framing_error(le),.data(lb),
        .packet_valid(lidar_packet_valid),.valid(lidar_valid),.point_valid(lidar_point),.angle_cdeg(lidar_angle),.distance_mm(lidar_distance),.confidence(lidar_confidence),
        .packet(lidar_packet),.sample_time(lidar_time),.sequence_id(lidar_seq),.errors(lidar_errors),.dropped(lidar_dropped),
        .front_mm(lidar_front),.left_mm(lidar_left),.right_mm(lidar_right));
    // Compatibility telemetry reserves these fields; no ToF hardware exists.
    assign tof_sda=1'bz;assign tof_scl=1'bz;assign tof_xshut=1'bz;
    assign tof_valid=0;assign tof_mm=65535;assign tof_status=255;
    assign tof_time=0;assign tof_seq=0;assign tof_errors=0;
endmodule
`default_nettype wire
