`timescale 1ns/1ps
module reverse_escape_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,tick=0,button_start=0,gyro_update=0;
 reg imu_valid=1,gyro_valid=1,tilt_valid=1,stationary=1,wheels_stationary=1;
 reg encoder_fault=0,cpu_alive=1,cpu_fault=0,lidar_valid=1,scan_valid=1;
 reg left_clear=0,right_clear=0;
 reg signed [15:0] raw_gz=0,roll=0,pitch=0,yaw=0;
 reg signed [31:0] left_count=0,right_count=0;
 reg [15:0] front=1500,left=300,right=300,rear=1000;
 wire armed,calibrated,lidar_enabled,motor_enable;wire signed [15:0] bias;
 wire [7:0] state,imu_fault_sources,imu_fault_valid_flags;wire [15:0] faults;
 wire signed [31:0] target_l,target_r;wire signed [15:0] imu_fault_roll,imu_fault_pitch;
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) dut(.*);
 task step;begin @(negedge clk);end endtask
 task control_tick;begin step;tick=1;ms_tick=1;step;tick=0;ms_tick=0;step;end endtask
 task start_session;
  begin
   rst_n=0;button_start=0;gyro_update=0;tick=0;ms_tick=0;
   imu_valid=1;gyro_valid=1;tilt_valid=1;encoder_fault=0;cpu_alive=1;cpu_fault=0;
   lidar_valid=1;scan_valid=1;left_clear=0;right_clear=0;
   roll=0;pitch=0;yaw=0;left_count=0;right_count=0;front=1500;left=300;right=300;rear=1000;
   repeat(4) step;rst_n=1;repeat(6) step;
   if(armed || motor_enable) $fatal(1,"automatic startup");
   button_start=1;step;button_start=0;
   repeat(64) begin gyro_update=1;step;gyro_update=0;step;end
   repeat(4) step;if(state!=2 || !motor_enable) $fatal(1,"start failed");
  end
 endtask
 task block_front;
  begin
   front=300;#1;if(motor_enable || target_l || target_r) $fatal(1,"front stop not immediate");
   control_tick;repeat(9) control_tick;
   if(state!=5 || motor_enable) $fatal(1,"reverse skipped the initial stop");
  end
 endtask
 task enter_reverse;
  begin block_front;control_tick;
   if(state!=10 || !motor_enable || target_l!=-60 || target_r!=-60 || faults)
    $fatal(1,"three blocked paths did not command bounded reverse");end
 endtask
 task assert_stopped;
  begin #1;if(motor_enable || target_l || target_r) $fatal(1,"reverse endpoint not immediate state=%0d motor=%0b targets=%0d/%0d rear=%0d counts=%0d/%0d button=%0b reset=%0b",state,motor_enable,target_l,target_r,rear,left_count,right_count,button_start,rst_n);end
 endtask
 initial begin
  start_session;rear=350;block_front;repeat(20) control_tick;
  if(state!=5 || motor_enable || faults) $fatal(1,"rear 350mm was allowed");
  rear=0;repeat(20) control_tick;
  if(state!=5 || motor_enable) $fatal(1,"zero rear was allowed");
  rear=65535;repeat(20) control_tick;
  if(state!=5 || motor_enable) $fatal(1,"unknown rear was allowed");
  rear=1000;front=301;repeat(20) control_tick;
  if(state!=5 || motor_enable) $fatal(1,"reversed without a blocked front");
  front=300;rear=351;control_tick;
  if(state!=10 || !motor_enable) $fatal(1,"rear 351mm failed to allow reverse");
  rear=350;assert_stopped;control_tick;
  if(state!=11 || faults) $fatal(1,"rear obstacle did not begin settling");
  rear=1000;repeat(400) control_tick;
  if(state!=5 || motor_enable || faults) $fatal(1,"reverse repeated without a new forward episode");

  start_session;left_count=123456;right_count=-456;enter_reverse;
  left_count=123456-704;#1;if(!motor_enable) $fatal(1,"left distance stopped early");
  left_count=123456-705;assert_stopped;control_tick;
  if(state!=11 || faults) $fatal(1,"left distance did not stop normally");
  left=600;left_clear=1;repeat(14) control_tick;
  if(state!=11 || motor_enable) $fatal(1,"reverse settling shorter than 150ms");
  control_tick;if(state!=5 || motor_enable) $fatal(1,"settling did not return to route selection");
  control_tick;if(state!=3 || target_l!=-80 || target_r!=80) $fatal(1,"did not choose reopened left path");
  yaw=15840;front=700;control_tick;repeat(15) control_tick;
  if(state!=2 || !motor_enable) $fatal(1,"turn did not return to forward with a new heading");
  left=300;left_clear=0;enter_reverse;

  start_session;enter_reverse;right_count=-705;#1;
  if(!motor_enable) $fatal(1,"right distance stopped early");
  right_count=-706;assert_stopped;control_tick;
  if(state!=11) $fatal(1,"right distance did not stop");

  start_session;left_count=32'h80000030;enter_reverse;
  left_count=left_count-705;assert_stopped;control_tick;
  if(state!=11) $fatal(1,"encoder wrap broke reverse distance");

  start_session;enter_reverse;repeat(198) control_tick;
  if(!motor_enable) $fatal(1,"missing encoder ended reverse before time bound");
  control_tick;assert_stopped;control_tick;
  if(state!=11 || faults) $fatal(1,"missing encoders did not stop at 2s");
  repeat(400) control_tick;if(state!=5 || motor_enable) $fatal(1,"timed retreat repeated");

  start_session;enter_reverse;rear=65535;assert_stopped;control_tick;
  if(state!=11) $fatal(1,"unknown rear did not stop reverse");
  start_session;enter_reverse;button_start=1;#1;
  if(motor_enable) $fatal(1,"S1 failed to revoke motor permission immediately");
  step;button_start=0;step;
  if(state!=0 || armed || motor_enable) $fatal(1,"S1 did not stop reverse");
  start_session;enter_reverse;scan_valid=0;assert_stopped;repeat(3) step;
  if(state!=8 || !faults[1] || armed) $fatal(1,"stale scan did not latch during reverse");
  start_session;enter_reverse;gyro_valid=0;assert_stopped;repeat(3) step;
  if(state!=8 || !faults[0] || imu_fault_sources!=2) $fatal(1,"IMU fault not preserved during reverse");
  start_session;enter_reverse;rst_n=0;assert_stopped;repeat(3) step;
  if(state!=0 || armed || motor_enable) $fatal(1,"S0/reset did not stop reverse");
  $display("PASS reverse: front 300/rear 350 boundaries, 100mm either wheel/wrap, 2s no-feedback bound, 150ms settle, one attempt, re-route and all stop gates");$finish;
 end
 initial begin #2000000;$fatal(1,"reverse watchdog");end
endmodule
