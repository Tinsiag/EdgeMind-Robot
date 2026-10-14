`timescale 1ns/1ps
module motion_stop_tb;
 reg clk=0,rstn=0;
 reg [7:0] ct=0;reg [255:0] cp=0;
 always #5 clk=~clk;
 motion_top #(.CLK_HZ(1000000)) dut(.clk(clk),.stop_n(rstn),.uart_rx(1'b1),.left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),.uart_tx(),.left_in1(),.left_in2(),.right_in1(),.right_in2(),.led());
 task cmd; input [7:0] t;input [255:0] p;
 begin
  @(negedge clk);ct=t;cp=p;
  force dut.cmd_type=ct;force dut.payload=cp;force dut.cmd_ttl=16'd250;force dut.cmd_valid=1'b1;
  @(negedge clk);release dut.cmd_valid;release dut.cmd_type;release dut.payload;release dut.cmd_ttl;
 end endtask
 task arm;begin cmd(8'h02,0);repeat(2) @(negedge clk);if(!dut.armed) $fatal(1,"ARM failed");end endtask
 integer i;
 initial begin
  repeat(4) @(negedge clk);rstn=1;repeat(10) @(negedge clk);
  for(i=0;i<7;i=i+1) cmd(8'h30,(256'd100<<8)|i);
  repeat(300000) @(negedge clk); // idle over 200 ms
  arm;cmd(8'h11,256'd50);repeat(100) @(negedge clk);
  if(dut.faults!=0) $fatal(1,"First motion after idle faulted");
  if(dut.monitor_r) $fatal(1,"Stationary wheel monitored");
  cmd(8'h04,0);repeat(4) @(negedge clk);
  if(dut.armed||dut.target_l!=0||dut.target_r!=0||dut.twist_pending) $fatal(1,"STOP stale target");
  arm;cmd(8'h12,(256'd50<<32)|256'd90000);repeat(10) @(negedge clk);
  if(!dut.rotate_active) $fatal(1,"Rotation not active");
  // A query payload must not change a rotation's saved speed.
  cmd(8'h20,0);repeat(4) @(negedge clk);
  if(dut.rot.saved_max_speed!=50) $fatal(1,"Rotation speed overwritten");
  cmd(8'h04,0);repeat(4) @(negedge clk);
  if(dut.rotate_active||dut.target_l!=0||dut.target_r!=0||dut.armed) $fatal(1,"STOP did not cancel rotate");
  arm;repeat(10) @(negedge clk);
  if(dut.rotate_active||dut.target_l!=0||dut.target_r!=0) $fatal(1,"Stale rotate restarted");
  cmd(8'h12,(256'd50<<32)|256'd90000);repeat(8) @(negedge clk);
  cmd(8'h03,0);repeat(4) @(negedge clk);
  if(dut.rotate_active||dut.armed) $fatal(1,"DISARM did not cancel");
  arm;cmd(8'h12,(256'd50<<32)|256'd90000);repeat(8) @(negedge clk);
  force dut.command_age=16'd251;@(negedge clk);release dut.command_age;
  repeat(4) @(negedge clk);
  if(dut.armed||dut.rotate_active||!dut.faults[0]) $fatal(1,"TTL did not stop/cancel");
  $display("PASS top idle first motion, stationary wheel, STOP/DISARM cancel, reARM, saved speed, TTL");$finish;
 end
 initial begin #10000000;$fatal(1,"Watchdog");end
endmodule
