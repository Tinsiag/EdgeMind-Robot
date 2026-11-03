`timescale 1ns/1ps
`default_nettype none
// Local-only start/stop is upstream. This module cannot ARM the supervisor.
module a745_motion_planner #(parameter READY_TICKS=100)(
 input wire clk,rst_n,tick,permission,input wire [1:0] mode,
 input wire signed [15:0] yaw,input wire signed [31:0] left_count,right_count,
 input wire [15:0] front,left,right,rear,
 input wire scan_valid,left_clear,right_clear,advance_clear,reverse_clear,left_exit_clear,right_exit_clear,spin_clear,
 input wire task_fresh,input wire [2:0] task_action,
 output reg enable,output reg signed [31:0] target_l,target_r,
 output reg [7:0] state,reason,output reg fault,
 output reg signed [31:0] rotation,output reg [7:0] route_stage
);
 localparam IDLE=0,FORWARD=2,LEFT=3,RIGHT=4,BLOCK=5,READY=6,SETTLE=9,BACK=10,REPLAN=11,SPIN=12,WAIT=13,DONE=14,TASK=15;
 reg active,reverse_used;reg [15:0] ticks,total_ticks;reg [7:0] stable_ticks;
 reg [1:0] selected;reg route_left;reg signed [15:0] original_yaw,last_yaw;
 reg signed [31:0] turn_goal,origin_l,origin_r,previous_l,previous_r;
 reg [31:0] cumulative_l,cumulative_r;
 reg [31:0] lateral_counts;reg [7:0] after_turn;
 wire signed [15:0] yaw_delta=yaw-last_yaw;
 wire signed [15:0] heading_error=original_yaw-yaw;
 wire signed [31:0] dl=left_count-origin_l,dr=right_count-origin_r;
 wire [31:0] al=dl[31] ? -dl:dl,ar=dr[31] ? -dr:dr;
 wire [32:0] travel_sum={1'b0,al}+{1'b0,ar};wire [31:0] travel=travel_sum[32:1];
 wire signed [31:0] sl=left_count-previous_l,sr=right_count-previous_r;
 wire [31:0] asl=sl[31] ? -sl:sl,asr=sr[31] ? -sr:sr;
 wire [32:0] next_l={1'b0,cumulative_l}+{1'b0,asl},next_r={1'b0,cumulative_r}+{1'b0,asr};
 wire turning=state==LEFT || state==RIGHT || state==SPIN;
 wire [31:0] abs_rotation=rotation[31] ? -rotation:rotation;
 wire [31:0] abs_goal=turn_goal[31] ? -turn_goal:turn_goal;
 wire reached=turn_goal[31] ? rotation<=turn_goal+546:rotation>=turn_goal-546;
 wire direction_ok=state==SPIN ? spin_clear:state==LEFT ? left_clear:right_clear;
 wire forward_ok=scan_valid && front>300 && front!=65535 && advance_clear;
 wire backward_ok=scan_valid && rear>350 && rear!=65535 && reverse_clear;
 wire can_left=scan_valid && left_clear && left_exit_clear;
 wire can_right=scan_valid && right_clear && right_exit_clear;
 wire side_exit=route_left ? can_right:can_left;
 wire [31:0] remaining=abs_goal>abs_rotation ? abs_goal-abs_rotation:0;
 wire signed [31:0] speed=remaining<5120 ? 40:80;
 // Outputs are combinationally revoked by hazards, stale task data, stop
 // permission or reached bounds. No multi-scan voting on the stop path.
 always @* begin
  enable=0;target_l=0;target_r=0;
  if(permission && !fault && scan_valid && (selected!=3 ||
     (task_fresh && (state==TASK || state==16 || state==READY || task_action==5))))begin
   if(state==FORWARD && forward_ok && (route_stage!=5 || travel<lateral_counts))begin
    enable=1;target_l=route_stage==0 && front>800 ? 120:60;target_r=target_l;
   end else if(turning && direction_ok && !reached)begin
    enable=1;target_l=turn_goal[31] ? speed:-speed;target_r=-target_l;
   end else if(state==BACK && backward_ok && al<705 && ar<706 && ticks<199)begin
    enable=1;target_l=-60;target_r=-60;
   end else if(state==TASK && task_fresh && ticks<49)begin
    if(task_action==1 && forward_ok && travel<1410)begin enable=1;target_l=60;target_r=60;end
    else if(task_action==2 && left_clear && rotation<1820)begin enable=1;target_l=-40;target_r=40;end
    else if(task_action==3 && right_clear && rotation > -1820)begin enable=1;target_l=40;target_r=-40;end
   end
  end
 end
 task begin_turn(input signed [31:0] goal,input [7:0] next_stage);
  begin state<=17;turn_goal<=goal;rotation<=0;last_yaw<=yaw;ticks<=0;after_turn<=next_stage;stable_ticks<=0;end
 endtask
 task finish(input [7:0] why);
  begin state<=DONE;reason<=why;ticks<=0;end
 endtask
 always @(posedge clk or negedge rst_n)
 if(!rst_n)begin
  state<=IDLE;reason<=0;fault<=0;active<=0;selected<=1;reverse_used<=0;ticks<=0;total_ticks<=0;stable_ticks<=0;
  rotation<=0;turn_goal<=0;last_yaw<=0;original_yaw<=0;origin_l<=0;origin_r<=0;previous_l<=0;previous_r<=0;cumulative_l<=0;cumulative_r<=0;
  lateral_counts<=0;route_stage<=0;route_left<=1;after_turn<=0;
 end else if(!permission)begin
  state<=IDLE;reason<=0;active<=0;fault<=0;rotation<=0;route_stage<=0;ticks<=0;total_ticks<=0;stable_ticks<=0;reverse_used<=0;
 end else if(!active)begin
  active<=1;selected<=mode;state<=READY;ticks<=0;total_ticks<=0;original_yaw<=yaw;last_yaw<=yaw;
  previous_l<=left_count;previous_r<=right_count;cumulative_l<=0;cumulative_r<=0;origin_l<=left_count;origin_r<=right_count;
 end else if(tick)begin
  last_yaw<=yaw;
  previous_l<=left_count;previous_r<=right_count;
  cumulative_l<=next_l[32] ? 32'hffffffff:next_l[31:0];
  cumulative_r<=next_r[32] ? 32'hffffffff:next_r[31:0];
  if(ticks<65535)ticks<=ticks+1'b1;
  if(total_ticks<65535)total_ticks<=total_ticks+1'b1;
  if(turning || (state==TASK && (task_action==2 || task_action==3)))rotation<=rotation+$signed(yaw_delta);
  if(selected==3 && state!=DONE && state!=READY && !task_fresh && ticks>=99)finish(8'd8);
  else if(selected==3 && state!=DONE && (total_ticks>=12000 || next_l>=21180 || next_r>=21180))finish(8'd9);
  // A STOP during a detour cancels that route. A later target/configuration
  // cannot resume the old path after its owner has withdrawn the command.
  else if(selected==3 && task_fresh && task_action==0 && state!=READY && state!=TASK && state!=16 && state!=DONE)begin
   state<=TASK;route_stage<=0;rotation<=0;ticks<=0;reason<=10;
   origin_l<=left_count;origin_r<=right_count;stable_ticks<=0;
  end
  else case(state)
   READY:if(ticks>=READY_TICKS-1)begin ticks<=0;
    if(selected==2)begin
     if(spin_clear)begin state<=SPIN;turn_goal<=65536;rotation<=0;last_yaw<=yaw;end
     else begin state<=WAIT;reason<=2;end
    end else if(selected==3)begin state<=TASK;reason<=0;end
    else state<=FORWARD;
   end
   WAIT:begin
    if(selected==2 && spin_clear)begin
     if(stable_ticks==19)begin state<=SPIN;turn_goal<=65536;rotation<=0;ticks<=0;stable_ticks<=0;end
     else stable_ticks<=stable_ticks+1'b1;
    end else stable_ticks<=0;
    if(ticks>=3000)finish(2);
   end
   FORWARD:begin
    if(!forward_ok)begin state<=BLOCK;ticks<=0;stable_ticks<=0;reason<=1;end
    else if(route_stage==1 || route_stage==3)begin
     if(side_exit && travel>=(route_stage==1 ? 2470:5645))begin
      if(stable_ticks<19)stable_ticks<=stable_ticks+1'b1;
      else if(route_stage==1)begin
       lateral_counts<=travel;begin_turn($signed(heading_error),2);
      end else begin_turn(route_left ? -32'sd16384:32'sd16384,4);
     end else stable_ticks<=0;
     if(travel>=10590 || ticks>=2500)finish(3);
    end else if(route_stage==5)begin
     if(travel>=lateral_counts)begin_turn($signed(heading_error),6);
     if(ticks>=2500)finish(3);
    end else begin reverse_used<=0;ticks<=0;end
   end
   BLOCK:begin
    if(ticks>=29)begin
     if(route_stage!=0)begin
      // A blocked detour is not permission to invent another unbounded route.
      if(forward_ok)begin state<=FORWARD;ticks<=0;end
      else if(ticks>=1000)finish(4);
     end else if(front>=600 && forward_ok)begin state<=FORWARD;ticks<=0;end
     else if(can_left || can_right)begin
      route_left<=can_left;route_stage<=0;
      begin_turn(can_left ? 32'sd16384:-32'sd16384,1);
     end else if(front<=300 && backward_ok && !reverse_used)begin
      state<=BACK;reverse_used<=1;ticks<=0;origin_l<=left_count;origin_r<=right_count;reason<=5;
     end
    end
   end
   LEFT,RIGHT,SPIN:begin
    if(!direction_ok)finish(2);
    else if(reached)begin state<=SETTLE;ticks<=0;end
    else if((turn_goal[31] && rotation>2731) || (!turn_goal[31] && rotation < -2731) ||
       (state==SPIN ? ticks>=2999:ticks>=449))begin fault<=1;reason<=6;end
   end
   17:if(ticks>=14)begin
    state<=turn_goal[31] ? RIGHT:LEFT;rotation<=0;last_yaw<=yaw;ticks<=0;
   end
   SETTLE:if(ticks>=14)begin
    if(selected==2)finish(0);
    else begin
     ticks<=0;origin_l<=left_count;origin_r<=right_count;stable_ticks<=0;
     case(after_turn)
      1:begin route_stage<=1;state<=FORWARD;end
      2:begin route_stage<=3;state<=FORWARD;end
      4:begin route_stage<=5;state<=FORWARD;end
      6:begin route_stage<=0;state<=selected==3 ? TASK:FORWARD;end
      default:finish(7);
     endcase
    end
   end
   BACK:if(!backward_ok || al>=705 || ar>=706 || ticks>=199)begin state<=REPLAN;ticks<=0;end
   REPLAN:if(ticks>=14)begin state<=BLOCK;ticks<=29;end
   TASK:begin
    if(!task_fresh)begin
     reason<=8;
     if(ticks>=99)finish(8);
    end else if(task_action==4)finish(0);
    else if(task_action==5)begin
     state<=BLOCK;ticks<=0;route_stage<=0;stable_ticks<=0;
     original_yaw<=yaw;reverse_used<=0;
    end
    else begin
     reason<=task_action==0 ? 10:0;
     if(task_action==0)begin origin_l<=left_count;origin_r<=right_count;ticks<=0;rotation<=0;end
     else if(ticks>=49 || (task_action==1 && travel>=1410) || rotation>=1820 || rotation<=-1820)begin
      // Each moving burst is at most 0.5s / 200mm. Require a STOP observation
      // between bursts; repeating a command cannot renew this local bound.
      state<=16;reason<=11;ticks<=0;
     end
    end
   end
   16:begin
    if(task_fresh && task_action==0)begin state<=TASK;ticks<=0;rotation<=0;origin_l<=left_count;origin_r<=right_count;end
    else if(ticks>=99)finish(8);
   end
   default:begin end
  endcase
 end
endmodule
`default_nettype wire
