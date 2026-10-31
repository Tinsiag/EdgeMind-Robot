`timescale 1ns/1ps
module imu_fault_latch_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,button_start=0,gyro_update=0,imu_valid=1,gyro_valid=1,tilt_valid=1;
 reg signed [15:0] roll=0,pitch=0;
 wire armed,motor_enable;wire [7:0] state,imu_fault_sources,imu_fault_valid_flags;
 wire signed [15:0] imu_fault_roll,imu_fault_pitch;wire [15:0] faults;
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) dut(.clk(clk),.rst_n(rst_n),.ms_tick(1'b0),.tick(1'b0),
  .button_start(button_start),.imu_valid(imu_valid),.gyro_valid(gyro_valid),.tilt_valid(tilt_valid),
  .stationary(1'b1),.gyro_update(gyro_update),.raw_gz(16'sd0),.roll(roll),.pitch(pitch),.yaw(16'sd0),
  .wheels_stationary(1'b1),.encoder_fault(1'b0),.left_count(32'sd0),.right_count(32'sd0),.rear(16'd350),.cpu_alive(1'b1),.cpu_fault(1'b0),
  .lidar_valid(1'b1),.scan_valid(1'b1),.front(16'd2000),.left(16'd2000),.right(16'd2000),
  .left_clear(1'b1),.right_clear(1'b1),.armed(armed),.motor_enable(motor_enable),.state(state),.faults(faults),
  .imu_fault_sources(imu_fault_sources),.imu_fault_valid_flags(imu_fault_valid_flags),
  .imu_fault_roll(imu_fault_roll),.imu_fault_pitch(imu_fault_pitch));
 task start_session;
  begin
   @(negedge clk);imu_valid=1;gyro_valid=1;tilt_valid=1;roll=0;pitch=0;button_start=1;
   @(negedge clk);button_start=0;
   if(imu_fault_sources || imu_fault_valid_flags) $fatal(1,"new calibration did not clear cause");
   repeat(64) begin gyro_update=1;@(negedge clk);gyro_update=0;@(negedge clk);end
   repeat(4) @(negedge clk);if(!armed || !motor_enable) $fatal(1,"start failed");
  end
 endtask
 task check_fault(input integer source,input integer captured_roll,input integer captured_pitch);
  begin
   #1;if(motor_enable) $fatal(1,"fault did not gate motor immediately");
   repeat(3) @(negedge clk);
   if(state!=8 || armed || faults!=1 || imu_fault_sources!=source ||
      imu_fault_roll!=captured_roll || imu_fault_pitch!=captured_pitch) $fatal(1,"wrong latched cause");
   imu_valid=1;gyro_valid=1;tilt_valid=1;roll=0;pitch=0;repeat(20) @(negedge clk);
   if(imu_fault_sources!=source || imu_fault_roll!=captured_roll || imu_fault_pitch!=captured_pitch || armed)
    $fatal(1,"recovered input erased fault-time evidence or restarted motion");
  end
 endtask
 initial begin
  repeat(4) @(negedge clk);rst_n=1;
  start_session();imu_valid=0;check_fault(1,0,0);
  start_session();gyro_valid=0;check_fault(2,0,0);
  start_session();tilt_valid=0;check_fault(4,0,0);
  start_session();roll=4097;pitch=-1024;check_fault(8,4097,-1024);
  start_session();imu_valid=0;gyro_valid=0;tilt_valid=0;roll=-8192;check_fault(15,-8192,0);
  $display("PASS fault-time IMU/gyro/attitude/tilt cause, atomic angles, evidence persistence and S1 clear without weakening stop");$finish;
 end
 initial begin #100000;$fatal(1,"fault latch watchdog");end
endmodule
