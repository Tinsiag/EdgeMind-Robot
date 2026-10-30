`timescale 1ns/1ps
module blocked_recovery_repro_tb;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,tick=0,button_start=0;
 reg imu_valid=1,gyro_valid=1,stationary=1,gyro_update=0,tilt_valid=1;
 reg signed [15:0] raw_gz=10,roll=0,pitch=0;
 reg wheels_stationary=1,encoder_fault=0,cpu_alive=1,cpu_fault=0,lidar_valid=1,scan_valid=1;
 reg [15:0] front=424,left=991,right=235,rear=800,nearest=235;
 wire armed,calibrated,lidar_enabled,motor_enable;
 wire signed [15:0] bias;
 wire [7:0] state; wire [15:0] faults;
 wire signed [31:0] target_l,target_r;
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) dut(.*);
 task step; begin @(negedge clk); end endtask
 task press; begin step;button_start=1;step;button_start=0;step;end endtask
 task control_tick; begin step;ms_tick=1;tick=1;step;ms_tick=0;tick=0;step;end endtask
 task calibrate; begin
  press;
  repeat(64) begin step;gyro_update=1;step;gyro_update=0;end
  repeat(3) step;
 end endtask
 integer cycle;
 initial begin
  // Match the observed front/right distances. Rear=800 is a controlled
  // rear-clear assumption matching entry into BACK, not a measured value.
  for(cycle=0;cycle<2;cycle=cycle+1) begin
   rst_n=0;front=424;left=991;right=235;rear=800;nearest=235;
   repeat(4) step;rst_n=1;repeat(4) step;
   if(armed || motor_enable || faults) $fatal(1,"cold reset not idle");
   calibrate;
   if(!armed || state!=2 || motor_enable || target_l || target_r)
    $fatal(1,"near front permitted forward output");
   control_tick;
   if(state!=5 || motor_enable) $fatal(1,"near envelope did not block turn");
   repeat(21) control_tick;
   if(state!=6 || target_l!=-60 || target_r!=-60) $fatal(1,"rear-clear bounded retreat missing");
   repeat(30) control_tick;
   if(state!=7 || motor_enable) $fatal(1,"near envelope permitted search turn");
   control_tick;
   if(state!=8 || faults!=16'h0020 || armed || motor_enable || target_l || target_r)
    $fatal(1,"observed recovery fault not reproduced");
   front=1500;left=1500;right=1500;rear=1500;nearest=1500;
   repeat(5) control_tick;
   if(state!=8 || armed || motor_enable) $fatal(1,"clearing obstacle auto-restarted motion");
   calibrate;
   if(state!=2 || !armed || !motor_enable || target_l!=120 || target_r!=120 || faults)
    $fatal(1,"fresh S1 with clearance failed");
   press;
   if(state!=0 || armed || motor_enable) $fatal(1,"S1 stop failed");
  end
  $display("PASS repeated cold reset: near-range ERR0020, no unsafe turn, fault latched, clear-space fresh S1 start and stop");
  $finish;
 end
 initial begin #1000000;$fatal(1,"reproduction timeout");end
endmodule
