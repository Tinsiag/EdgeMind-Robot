`timescale 1ns/1ps
module autonomy_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,tick=0,button_start=0,imu_valid=1,gyro_valid=1,stationary=1,gyro_update=0,tilt_valid=1;
 reg signed [15:0] raw_gz=10,roll=0,pitch=0,yaw=0;
 reg wheels_stationary=1,encoder_fault=0,cpu_alive=1,cpu_fault=0,lidar_valid=1,scan_valid=1,left_clear=1,right_clear=1;
 reg [15:0] front=1500,left=1500,right=1500,rear=350;
 reg signed [31:0] left_count=0,right_count=0;
 wire armed,calibrated,lidar_enabled,motor_enable;wire signed [15:0] bias;
 wire [7:0] state;wire [15:0] faults;wire signed [31:0] target_l,target_r;
 wire [7:0] imu_fault_sources,imu_fault_valid_flags;wire signed [15:0] imu_fault_roll,imu_fault_pitch;
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) dut(.*);
 task step;begin @(negedge clk);end endtask
 task press;begin step;button_start=1;step;button_start=0;step;end endtask
 task control_tick;begin step;ms_tick=1;tick=1;step;ms_tick=0;tick=0;step;end endtask
 task start_local;
  begin
   press;repeat(64) begin step;gyro_update=1;step;gyro_update=0;end
   repeat(3) step;
   if(!armed || !calibrated || bias!=10 || state!=2) $fatal(1,"local calibration/start failed");
  end
 endtask
 initial begin
  repeat(4) step;rst_n=1;repeat(8) step;
  if(armed || motor_enable || lidar_enabled) $fatal(1,"automatic startup");
  start_local;
  front=1000;control_tick;if(state!=2 || target_l!=120) $fatal(1,"stopped at one metre");
  front=501;control_tick;if(state!=2 || target_l!=60 || !motor_enable) $fatal(1,"stopped above 300mm");
  front=301;control_tick;if(state!=2 || target_l!=60 || !motor_enable) $fatal(1,"301mm did not remain forward");
  front=300;left=900;right=1200;right_clear=0;#1;
  if(motor_enable || target_l || target_r) $fatal(1,"300mm boundary not gated immediately");
  control_tick;repeat(10) control_tick;
  if(state!=3 || target_l!=-80 || target_r!=80) $fatal(1,"did not choose only safe left path");
  // Open forward space alone must not end a gyro-targeted turn.
  front=1800;repeat(20) control_tick;if(state!=3) $fatal(1,"timer or front range ended gyro turn early");
  yaw=14000;control_tick;if(target_l!=-40 || target_r!=40) $fatal(1,"no proportional turn deceleration");
  yaw=15840;#1;if(motor_enable || target_l || target_r) $fatal(1,"gyro braking boundary not immediate");
  control_tick;if(state!=9) $fatal(1,"no turn settling");
  repeat(15) control_tick;if(state!=2 || !motor_enable) $fatal(1,"turn did not resume straight");
  press;if(armed || motor_enable || lidar_enabled) $fatal(1,"S1 stop");
  // Prefer the longer safe passage and handle the +/-180 degree boundary.
  front=1500;left=700;right=1400;left_clear=1;right_clear=1;yaw=-30000;start_local;
  front=300;control_tick;repeat(10) control_tick;
  if(state!=4 || target_l!=80 || target_r!=-80) $fatal(1,"did not choose longer right passage");
  yaw=19696;front=1800;#1;if(motor_enable) $fatal(1,"wrapped right yaw did not brake");
  control_tick;repeat(15) control_tick;if(state!=2) $fatal(1,"wrapped right turn did not finish");
  // A new point in the selected swept space must stop the turn immediately.
  front=300;left=1400;right=700;control_tick;repeat(10) control_tick;
  if(state!=3) $fatal(1,"left entry missing");
  left_clear=0;#1;if(motor_enable || target_l || target_r) $fatal(1,"new swept obstacle not immediate");
  control_tick;if(state!=5) $fatal(1,"swept obstacle did not enter wait");
  right_clear=0;repeat(600) control_tick;
  if(state!=5 || motor_enable || faults || !armed) $fatal(1,"both blocked did not wait safely");
  press;front=1500;left_clear=1;right_clear=1;start_local;encoder_fault=1;#1;
  if(motor_enable) $fatal(1,"encoder failure not immediate");
  repeat(3) step;encoder_fault=0;repeat(3) step;
  if(state!=8 || armed || !faults[2]) $fatal(1,"encoder failure not latched");
  start_local;lidar_valid=0;repeat(3) step;lidar_valid=1;repeat(3) step;
  if(state!=8 || armed || !faults[1]) $fatal(1,"lidar restore auto-started");
  start_local;cpu_fault=1;repeat(3) step;cpu_fault=0;repeat(3) step;
  if(state!=8 || armed || !faults[3]) $fatal(1,"CPU failure not latched");
  start_local;front=300;control_tick;repeat(10) control_tick;
  repeat(450) control_tick;
  if(state!=8 || armed || !faults[7]) $fatal(1,"missing gyro progress not timed out");
  cpu_alive=0;front=1500;press;
  repeat(64) begin step;gyro_update=1;step;gyro_update=0;end
  repeat(10003) control_tick;
  if(state!=8 || faults[4:3]!=2'b11 || armed) $fatal(1,"CPU startup timeout not identified");
  cpu_alive=1;repeat(5) step;if(armed || state!=8) $fatal(1,"CPU restore auto-started");
  $display("PASS autonomous 300mm boundary, directional selection, gyro turn/settle/wrap, blocked wait, safety faults and startup gates");$finish;
 end
 initial begin #2000000;$fatal(1,"autonomy watchdog");end
endmodule
