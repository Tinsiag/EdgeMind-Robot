`timescale 1ns/1ps
module attitude_session_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,sample_update=0,sample_valid=1,button_start=0,gyro_update=0;
 reg signed [15:0] ax=0,ay=600,az=16384;
 wire signed [15:0] roll,pitch,bias;wire tilt_valid,done,armed,calibrated,motor_enable,lidar_enabled;
 wire [7:0] state;wire [15:0] faults;wire signed [31:0] target_l,target_r;
 a741_attitude attitude(.clk(clk),.rst_n(rst_n),.sample_update(sample_update),.sample_valid(sample_valid),
  .ax(ax),.ay(ay),.az(az),.roll(roll),.pitch(pitch),.valid(tilt_valid),.done(done));
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) session(.clk(clk),.rst_n(rst_n),.ms_tick(1'b0),.tick(1'b0),
  .button_start(button_start),.imu_valid(sample_valid),.gyro_valid(sample_valid),.stationary(1'b1),
  .gyro_update(gyro_update),.tilt_valid(tilt_valid),.raw_gz(16'sd10),.roll(roll),.pitch(pitch),
  .wheels_stationary(1'b1),.encoder_fault(1'b0),.left_count(32'sd0),.right_count(32'sd0),.rear(16'd350),.cpu_alive(1'b1),.cpu_fault(1'b0),
  .lidar_valid(1'b1),.scan_valid(1'b1),.front(16'd2000),.left(16'd2000),.right(16'd2000),
  .yaw(16'sd0),.left_clear(1'b1),.right_clear(1'b1),.armed(armed),.calibrated(calibrated),.bias(bias),
  .lidar_enabled(lidar_enabled),.motor_enable(motor_enable),.state(state),.faults(faults),
  .target_l(target_l),.target_r(target_r));
 task sample;
  begin @(negedge clk);sample_update=1;gyro_update=1;
   @(negedge clk);sample_update=0;gyro_update=0;repeat(80) @(negedge clk);end
 endtask
 task start_session;
  begin @(negedge clk);button_start=1;@(negedge clk);button_start=0;
   repeat(64) sample();repeat(4) @(negedge clk);
   if(!armed || !motor_enable || faults) $fatal(1,"stationary calibration did not ARM");end
 endtask
 initial begin
  #30;rst_n=1;sample();start_session();
  repeat(6) begin sample();if(!armed || !motor_enable || faults) $fatal(1,"fresh attitude update killed motion: state=%d faults=%h",state,faults);end
  // One acceleration/vibration spike must not become a false over-tilt.
  ay=12000;az=12000;sample();
  if(!armed || !motor_enable || faults) $fatal(1,"single-sample attitude spike caused a stop");
  ay=600;az=16384;sample();
  if(!armed || !motor_enable || faults) $fatal(1,"attitude did not recover after isolated spike");
  // A genuinely invalid gravity triad must still stop immediately.
  ax=0;ay=0;az=0;sample();
  if(armed || motor_enable || state!=8 || !faults[0]) $fatal(1,"invalid sample did not stop");
  az=16384;sample();if(armed || state!=8) $fatal(1,"sensor restore auto-started");
  start_session();sample_valid=0;repeat(4) @(negedge clk);
  if(armed || motor_enable || !faults[0]) $fatal(1,"stale sample did not stop");
  sample_valid=1;sample();start_session();ax=16384;az=1000;sample();
  if(!armed || !motor_enable || faults) $fatal(1,"single tilt sample bypassed median");
  sample();
  if(armed || motor_enable || !faults[0]) $fatal(1,"real excessive tilt did not stop");
  $display("PASS real CORDIC + autonomy: isolated shock keeps motion; sustained tilt stops on second sample; invalid/stale stop and latch");$finish;
 end
 initial begin #2000000;$fatal(1,"attitude/session watchdog");end
endmodule
