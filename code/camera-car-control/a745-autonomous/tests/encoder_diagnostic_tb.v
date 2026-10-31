`timescale 1ns/1ps
// Exercise the real core wiring, counters, quadrature decoder and autonomy.
// Force only sensor/CPU boundary signals, not encoder paths or fault inputs.
module encoder_diagnostic_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,button_start=0,left_a=0,left_b=0,right_a=0,right_b=0;
 reg test_tick=0,test_ms=0,test_gyro_update=0;
 wire [895:0] snapshot;wire [255:0] fusion_snapshot;wire [7:0] state;wire [15:0] faults;
 tri1 imu_sda,imu_scl;
 a745_core #(.GEOMETRY_VERIFIED(1)) dut(.clk(clk),.rst_n(rst_n),.button_start(button_start),
  .imu_int(1'b0),.lidar_rx(1'b1),.imu_sda(imu_sda),.imu_scl(imu_scl),
  .left_a(left_a),.left_b(left_b),.right_a(right_a),.right_b(right_b),
  .phy_ready(1'b0),.phy_error(1'b0),.mac_diagnostic(8'd0),.eth_tx_ready(1'b1),
  .ddr_ready(1'b1),.frame_ready(1'b1),.camera_error(1'b0),.ddr_error(1'b0),.video_overflow(1'b0),
  .video_frames(32'd0),.camera_diagnostic(48'd0),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.state(state),.faults(faults));
 task control_tick;
  begin @(negedge clk);test_tick=1;test_ms=1;@(negedge clk);test_tick=0;test_ms=0;repeat(32) @(negedge clk);end
 endtask
 initial begin
  force dut.tick=test_tick;force dut.ms_tick=test_ms;
  force dut.iv=1;force dut.gv=1;force dut.tilt=1;force dut.stationary=1;
  force dut.gu=test_gyro_update;force dut.raw=0;force dut.roll=0;force dut.pitch=0;force dut.yaw=0;
  force dut.cpu_alive=1;force dut.cpu_fault=0;
  force dut.lv=1;force dut.scan_valid=1;force dut.front=1500;force dut.left=1000;force dut.right=1000;
  force dut.rear=1000;force dut.left_clear=1;force dut.right_clear=1;
  repeat(4) @(negedge clk);rst_n=1;repeat(8) @(negedge clk);
  if(dut.armed || dut.motor_enable) $fatal(1,"auto ARM");
  button_start=1;@(negedge clk);button_start=0;
  repeat(64) begin test_gyro_update=1;@(negedge clk);test_gyro_update=0;@(negedge clk);end
  repeat(4) @(negedge clk);
  if(state!=2 || !dut.motor_enable) $fatal(1,"core start failed");
  repeat(101) control_tick;
  if(!dut.lto || !dut.rto || faults || state!=2 || !dut.motor_enable || !snapshot[162] || !snapshot[167])
   $fatal(1,"no-pulse timeout still stopped core or telemetry missing");
  if(snapshot[159:128]!=74508 || dut.lc!=0 || dut.rc!=0 || dut.pl.command<=0 || dut.pr.command<=0)
   $fatal(1,"identity/counter/PI path changed");
  // One real, valid AB edge clears only the left warning and updates count.
  left_b=1;repeat(10) @(negedge clk);control_tick;
  if(dut.lc!=1 || dut.lto || !dut.rto || snapshot[162] || !snapshot[167] || faults)
   $fatal(1,"real encoder edge did not independently clear warning");
  // Two-bit transitions remain invalid and still latch ERR0004.
  repeat(65) begin left_a=~left_a;left_b=~left_b;repeat(8) @(negedge clk);end
  repeat(4) @(negedge clk);
  if(state!=8 || dut.armed || dut.motor_enable || faults!=4 || dut.invalid_l!=65)
   $fatal(1,"illegal quadrature no longer stops the core");
  button_start=1;#1;if(dut.motor_enable) $fatal(1,"S1 did not gate motor");
  @(negedge clk);button_start=0;rst_n=0;repeat(3) @(negedge clk);
  if(dut.motor_enable || state!=0) $fatal(1,"reset stop failed");
  $display("PASS actual core: 1s no-pulse is telemetry only, real edge/count/PI preserved, illegal quadrature still latches ERR0004, S1/reset stop");$finish;
 end
 initial begin #2000000;$fatal(1,"encoder diagnostic watchdog");end
endmodule
