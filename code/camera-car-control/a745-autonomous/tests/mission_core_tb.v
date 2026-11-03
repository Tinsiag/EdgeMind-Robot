`timescale 1ns/1ps
module mission_core_tb;
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
  repeat(4)@(negedge clk);rst_n=1;repeat(10)ct;
  if(dut.armed || dut.motor_enable || dut.pl.command || dut.pr.command)$fatal(1,"network request armed idle core");
  start;if(state!=15 || !dut.motor_enable || dut.target_l!=-40 || dut.target_r!=40)$fatal(1,"mode3 actual core route");
  task_fresh=0;#1;if(dut.motor_enable)$fatal(1,"stale network output");
  task_fresh=1;force dut.camera_age_ms=600;#1;if(dut.motor_enable)$fatal(1,"stale camera output");force dut.camera_age_ms=0;
  press;if(dut.motor_enable || dut.armed)$fatal(1,"S1 actual core stop");
  selected_mode=1;start;if(state!=2 || dut.target_l!=120)$fatal(1,"mode1 actual core");
  task_action=3;task_fresh=0;repeat(3)ct;if(dut.target_l!=120 || !dut.motor_enable)$fatal(1,"network affected local mode");
  press;selected_mode=2;start;
  if(state!=12 || !dut.motor_enable)$fatal(1,"mode2 actual core");
  task_action=4;task_fresh=1;repeat(3)ct;
  if(state!=12 || dut.target_l!=-80 || dut.target_r!=80)$fatal(1,"network affected mode2");
  press;selected_mode=1;start;
  force dut.front=300;#1;if(dut.motor_enable || dut.target_l)$fatal(1,"front interlock bypassed");
  force dut.iv=0;repeat(5)@(negedge clk);
  if(state!=8 || !faults[0] || dut.armed || dut.motor_enable)$fatal(1,"real IMU supervision lost");
  $display("PASS connected advanced core: no network ARM, bounded mode3 routing, camera/link freshness, S1 stop, mode1 network isolation and real IMU fault latch");$finish;
 end
 initial begin #2000000;$fatal(1,"mission core timeout");end
endmodule
