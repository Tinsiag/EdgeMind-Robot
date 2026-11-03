`timescale 1ns/1ps
module local_offline_startup_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,button_start=0,test_tick=0,test_ms=0,gu=0,task_fresh=1;
 reg [1:0] selected_mode=3;reg [2:0] task_action=2;
 wire [7:0] state;wire [15:0] faults;wire [895:0] snapshot;wire [255:0] fusion_snapshot;
 tri1 imu_sda,imu_scl;
 a745_core #(.ADVANCED(1),.GEOMETRY_VERIFIED(1)) dut(.clk(clk),.rst_n(rst_n),.button_start(button_start),
  .selected_mode(selected_mode),.task_fresh(task_fresh),.task_action(task_action),.task_session(32'd100),.network_video_frame(32'd100),.task_accepted(8'd0),
  .imu_int(1'b0),.lidar_rx(1'b1),.imu_sda(imu_sda),.imu_scl(imu_scl),
  .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),.phy_ready(1'b0),.phy_error(1'b0),.mac_diagnostic(8'd0),.eth_tx_ready(1'b1),
  .ddr_ready(1'b1),.frame_ready(1'b1),.camera_error(1'b0),.ddr_error(1'b0),.video_overflow(1'b0),.video_frames(32'd100),.camera_diagnostic(48'd0),
  .snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.state(state),.faults(faults));
 task ct;begin @(negedge clk);test_tick=1;test_ms=1;@(negedge clk);test_tick=0;test_ms=0;repeat(32)@(negedge clk);end endtask
 task press;begin @(negedge clk);button_start=1;@(negedge clk);button_start=0;repeat(4)@(negedge clk);end endtask
 task start;begin press;repeat(64)begin gu=1;@(negedge clk);gu=0;@(negedge clk);end repeat(105)ct;end endtask
 initial begin
  force dut.tick=test_tick;force dut.ms_tick=test_ms;force dut.iv=1;force dut.gv=1;force dut.tilt=1;force dut.stationary=1;
  force dut.gu=gu;force dut.raw=0;force dut.roll=0;force dut.pitch=0;force dut.yaw=0;
  force dut.wheel_quiet_ms=200;force dut.camera_age_ms=0;force dut.cpu_alive=1;force dut.cpu_fault=0;
  force dut.lv=1;force dut.scan_valid=1;force dut.front=1500;force dut.left=500;force dut.right=500;force dut.rear=1000;
  force dut.left_clear=1;force dut.right_clear=1;force dut.advance_clear=1;force dut.reverse_clear=1;
  force dut.left_exit_clear=1;force dut.right_exit_clear=1;force dut.spin_clear=1;
  force dut.camera_age_ms=1000;task_fresh=0;
  repeat(4)@(negedge clk);rst_n=1;repeat(10)ct;
  selected_mode=1;start;
  if(state!=2 || faults || !dut.motor_enable || dut.target_l!=120)
   $fatal(1,"offline mode1 start failed");
  press;selected_mode=2;start;
  if(state!=12 || faults || !dut.motor_enable || dut.target_l!=-80 || dut.target_r!=80)
   $fatal(1,"offline mode2 start failed");
  press;selected_mode=1;force dut.stationary=0;press;
  repeat(10003)ct;
  if(state!=8 || faults!=16'h0011 || dut.imu_fault_sources!=8'h30 || dut.armed || dut.motor_enable)
   $fatal(1,"0011 stationary timeout decode");
  force dut.stationary=1;press;repeat(10003)ct;
  if(state!=8 || faults!=16'h0011 || dut.imu_fault_sources!=8'h20 || dut.armed || dut.motor_enable)
   $fatal(1,"0011 gyro samples timeout decode");
  force dut.iv=0;force dut.gv=0;force dut.tilt=0;force dut.stationary=0;press;
  repeat(10003)ct;
  if(state!=8 || faults!=16'h0011 || dut.imu_fault_sources!=8'h37 || dut.imu_fault_valid_flags[2:0]!=0 || dut.armed || dut.motor_enable)
   $fatal(1,"reported 0011/SRC37 invalid IMU startup");
  $display("PASS local modes1/2 with PHY down, stale camera and absent task network; ERR0011 calibration timeout SRC30/SRC20/SRC37; no motion permission on failure");$finish;
 end
 initial begin #15000000;$fatal(1,"offline startup watchdog");end
endmodule
