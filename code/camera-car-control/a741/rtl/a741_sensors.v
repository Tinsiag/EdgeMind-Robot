`timescale 1ns/1ps
`default_nettype none
module a741_sensors #(parameter CLK_HZ=50000000,AUX_ENABLED=1,ALLOW_MPU6500=0,
    LIDAR_ENABLED=AUX_ENABLED,TOF_ENABLED=AUX_ENABLED)(
    input wire clk,rst_n,ms_tick,lidar_rx,imu_int,calibrated,
    input wire signed [15:0] gyro_bias,
    inout wire imu_sda,imu_scl,
    inout wire tof_sda,tof_scl,tof_xshut,
    output wire imu_valid,angle_update,gyro_valid,gyro_update,imu_stationary,
    output wire signed [15:0] yaw,roll,pitch,gx,gy,gz,
    output wire [31:0] now_ms,imu_time,gyro_time,imu_seq,imu_errors,imu_diagnostic,
    output wire [95:0] imu_raw,output wire [15:0] imu_temperature,
    output wire tof_valid,output wire [15:0] tof_mm,
    output wire [7:0] tof_status,output wire [31:0] tof_time,tof_seq,tof_errors,
    output wire lidar_valid,lidar_packet_valid,output wire [375:0] lidar_packet,
    output wire [31:0] lidar_time,lidar_seq,lidar_errors,lidar_dropped,
    output wire [15:0] lidar_front,lidar_left,lidar_right
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
    // No synthetic roll/pitch attitude is presented as a measured angle.
    assign roll=0;assign pitch=0;
    ld06_parser lidar(.clk(clk),.rst_n(rst_n && LIDAR_ENABLED!=0),.ms_tick(ms_tick),.byte_valid(lv),.framing_error(le),.data(lb),
        .packet_valid(lidar_packet_valid),.valid(lidar_valid),.point_valid(),.angle_cdeg(),.distance_mm(),.confidence(),
        .packet(lidar_packet),.sample_time(lidar_time),.sequence_id(lidar_seq),.errors(lidar_errors),.dropped(lidar_dropped),
        .front_mm(lidar_front),.left_mm(lidar_left),.right_mm(lidar_right));
    wire start,read,busy,done,xerror,low,init,error,update,svalid;
    wire [15:0] regaddr,range_mm;wire [2:0] count;wire [31:0] wd,rd;wire [7:0] status;
    // Failed initialization is retried only while the control layer sees invalid
    // data. A latched motion fault still requires a separate manual clear/ARM.
    reg [15:0] retry_age,age;reg retry_reset;
    reg [31:0] stamp,seq,errs;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin retry_age<=0;age<=65535;retry_reset<=0;stamp<=0;seq<=0;errs<=0;end
        else begin
            retry_reset<=0;
            if(ms_tick) begin
                if(age!=65535) age<=age+1'b1;
                if(error) begin
                    if(retry_age==1999) begin retry_reset<=1;retry_age<=0;errs<=errs+1'b1;end
                    else retry_age<=retry_age+1'b1;
                end else retry_age<=0;
            end
            if(update) begin age<=0;stamp<=now_ms;seq<=seq+1'b1;end
        end
    wire trst=rst_n && !retry_reset && TOF_ENABLED!=0;
    assign tof_xshut=low || !trst ? 1'b0:1'bz;
    i2c_reg_master #(.CLK_HZ(CLK_HZ)) bus(.clk(clk),.rst_n(trst),.start(start),.read(read),.address(7'h29),
        .reg_addr(regaddr),.byte_count(count),.write_data(wd),.read_data(rd),.busy(busy),.done(done),.error(xerror),.sda(tof_sda),.scl(tof_scl));
    vl53l1x_driver tof(.clk(clk),.rst_n(trst),.ms_tick(ms_tick),.xshut_low(low),.xfer_start(start),.xfer_read(read),
        .xfer_reg(regaddr),.xfer_count(count),.xfer_write(wd),.xfer_busy(busy),.xfer_done(done),.xfer_error(xerror),.xfer_data(rd),
        .init_done(init),.error(error),.sample_update(update),.sample_valid(svalid),.distance_mm(range_mm),.range_status(status));
    assign tof_valid=init && svalid && !error && age<150;
    assign tof_mm=range_mm;assign tof_status=status;assign tof_time=stamp;assign tof_seq=seq;assign tof_errors=errs;
endmodule
`default_nettype wire
