`timescale 1ns/1ps
module motion_planner_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,tick=0,permission=0;reg [1:0] mode=1;
 reg signed [15:0] yaw=0;reg signed [31:0] left_count=0,right_count=0;
 reg [15:0] front=1500,left=500,right=500,rear=1000;
 reg scan_valid=1,left_clear=1,right_clear=1,advance_clear=1,reverse_clear=1,left_exit_clear=1,right_exit_clear=1,spin_clear=1;
 reg task_fresh=0;reg [2:0] task_action=0;
 wire enable,fault;wire signed [31:0] target_l,target_r,rotation;wire [7:0] state,reason,route_stage;
 a745_motion_planner #(.READY_TICKS(2)) dut(.*);
 task step;begin @(negedge clk);end endtask
 task ct;begin step;tick=1;step;tick=0;step;end endtask
 task start(input [1:0] m);begin permission=0;repeat(3)step;mode=m;permission=1;repeat(4)ct;end endtask
 task quarter(input integer sign);integer i;begin
  repeat(16)ct;
  for(i=0;i<90;i=i+1)begin yaw=yaw+sign*182;ct;end
  repeat(18)ct;
 end endtask
 integer i;
 initial begin
  repeat(4)step;rst_n=1;repeat(4)step;
  if(enable)$fatal(1,"automatic movement");start(1);
  if(state!=2 || target_l!=120)$fatal(1,"mode1 start");
  // Both sides 50cm cannot cause reverse while the front is open.
  repeat(50)ct;if(state!=2)$fatal(1,"side 50cm caused escape");
  front=300;#1;if(enable)$fatal(1,"front boundary not immediate");
  ct;repeat(31)ct;if(state!=17 || enable)$fatal(1,"geometric left exit/braking at 50cm");
  front=1500;quarter(1);if(state!=2 || route_stage!=1)$fatal(1,"lateral segment missing");
  left_count=3000;right_count=3000;repeat(23)ct;
  if(state!=17)$fatal(1,"restore original heading missing");quarter(-1);
  if(state!=2 || route_stage!=3)$fatal(1,"parallel segment missing");
  left_count=9000;right_count=9000;repeat(23)ct;
  if(state!=17)$fatal(1,"return-to-line turn missing");quarter(-1);
  left_count=12000;right_count=12000;ct;
  if(state!=17)$fatal(1,"final heading restoration missing");quarter(1);
  if(state!=2 || route_stage!=0)$fatal(1,"route did not complete");
  start(2);if(state!=12)$fatal(1,"spin missing");
  for(i=0;i<180;i=i+1)begin yaw=yaw+182;ct;end
  if(state!=12 || rotation<32000)$fatal(1,"stopped at half-turn");
  for(i=0;i<180;i=i+1)begin yaw=yaw+182;ct;end
  repeat(20)ct;if(state!=14 || enable)$fatal(1,"360 wrap/completion");
  start(2);spin_clear=0;#1;if(enable)$fatal(1,"spin obstacle did not stop immediately");ct;
  if(state!=14)$fatal(1,"spin hazard not terminal");spin_clear=1;
  start(1);front=300;left_exit_clear=0;right_exit_clear=0;ct;repeat(31)ct;
  if(state!=10 || target_l!=-60)$fatal(1,"true blocked reverse missing");
  left_count=left_count+705;#1;if(enable)$fatal(1,"reverse bound");ct;repeat(250)ct;
  if(state!=5)$fatal(1,"reverse repeated");
  front=1500;start(3);task_fresh=1;task_action=1;ct;
  if(!enable)$fatal(1,"local task permission missing");task_fresh=0;#1;if(enable)$fatal(1,"expired task did not stop");
  repeat(110)ct;if(state!=14)$fatal(1,"link loss not terminal");
  task_fresh=1;repeat(5)ct;if(enable)$fatal(1,"link return restarted");
  start(3);task_action=2;repeat(52)ct;if(enable)$fatal(1,"task burst unbounded");
  task_action=0;repeat(3)ct;task_action=2;ct;if(!enable)$fatal(1,"STOP did not rearm bounded burst");
  task_action=5;ct;front=300;left_exit_clear=1;repeat(32)ct;
  if(state!=17)$fatal(1,"task detour missing");task_action=0;ct;
  if(state!=15 || route_stage!=0 || enable)$fatal(1,"STOP did not cancel old detour");
  front=1500;start(3);task_action=0;
  // Net displacement returns to zero, but actual travel must still exhaust
  // the 3m wheel budget. This catches cancellation by reversing direction.
  for(i=0;i<12;i=i+1)begin left_count=left_count+2000;ct;left_count=left_count-2000;ct;end
  if(state!=14 || reason!=9 || enable)$fatal(1,"cumulative task travel unbounded");
  permission=0;#1;if(enable)$fatal(1,"local stop");
  $display("PASS modes, 50cm sides, complete four-turn detour, full yaw wrap, one reverse, local stop and bounded stale task");$finish;
 end
 initial begin #1000000;$fatal(1,"planner timeout");end
endmodule
