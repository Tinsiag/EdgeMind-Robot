`timescale 1ns/1ps
`default_nettype none
// Local S1 owns calibration/ARM. Obstacles cause a measured quarter-turn or
// a stationary wait; CPU/IMU/encoder faults always revoke motor permission.
module a745_autonomy #(parameter GEOMETRY_VERIFIED=0,STOP_MM=500,CLEAR_MM=600,SLOW_MM=800)(
 input wire clk,rst_n,ms_tick,tick,button_start,
 input wire imu_valid,gyro_valid,stationary,gyro_update,tilt_valid,
 input wire signed [15:0] raw_gz,roll,pitch,yaw,
 input wire wheels_stationary,encoder_fault,cpu_alive,cpu_fault,lidar_valid,scan_valid,
 input wire [15:0] front,left,right,input wire left_clear,right_clear,
 output reg armed,calibrated,output reg signed [15:0] bias,
 output wire lidar_enabled,motor_enable,output reg [7:0] state,
 output reg [15:0] faults,output reg signed [31:0] target_l,target_r
);
 localparam IDLE=0,CALIBRATE=1,FORWARD=2,LEFT=3,RIGHT=4,BLOCKED=5,FAULT=8,SETTLE=9;
 reg [13:0] age;reg [6:0] samples;reg signed [31:0] bias_sum;
 reg [8:0] turn_ticks;reg [3:0] wait_ticks;reg signed [15:0] turn_origin;
 wire running=state==FORWARD || state==LEFT || state==RIGHT || state==BLOCKED || state==SETTLE;
 wire turning=state==LEFT || state==RIGHT;
 wire sensors_ok=imu_valid && gyro_valid && tilt_valid && lidar_valid && scan_valid;
 wire tilt_bad=roll>4096 || roll < -4096 || pitch>4096 || pitch < -4096;
 wire safe=armed && sensors_ok && !encoder_fault && cpu_alive && !cpu_fault && !tilt_bad && faults==0;
 // Subtract in 16 bits first: the gyro wraps at +/-180 degrees.
 wire signed [15:0] wrapped_delta=yaw-turn_origin;
 wire signed [16:0] turn_progress=state==RIGHT ? -$signed({wrapped_delta[15],wrapped_delta}):$signed({wrapped_delta[15],wrapped_delta});
 wire signed [16:0] turn_remaining=17'sd16384-turn_progress;
 wire signed [16:0] proportional_speed=turn_remaining >>> 7;
 wire signed [31:0] turn_speed=proportional_speed>80 ? 32'sd80:proportional_speed<40 ? 32'sd40:32'(proportional_speed);
 // 87 degrees is the braking boundary for a 90-degree target, not a timer.
 wire turn_reached=turn_progress>=17'sd15838;
 wire direction_clear=state==LEFT ? left_clear:right_clear;
 wire can_left=left_clear && left>=CLEAR_MM && left!=65535;
 wire can_right=right_clear && right>=CLEAR_MM && right!=65535;
 wire clearance_ok=turning ? direction_clear && !turn_reached:front>STOP_MM && front!=65535;
 assign motor_enable=rst_n && safe && (state==FORWARD || turning) && clearance_ok && !button_start;
 assign lidar_enabled=state!=IDLE && state!=FAULT;
 always @* begin
  target_l=0;target_r=0;
  if(safe && clearance_ok) case(state)
   FORWARD:begin target_l=front>SLOW_MM ? 120:60;target_r=target_l;end
   LEFT:begin target_l=-turn_speed;target_r=turn_speed;end
   RIGHT:begin target_l=turn_speed;target_r=-turn_speed;end
   default:begin end
  endcase
 end
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin state<=IDLE;armed<=0;calibrated<=0;bias<=0;faults<=0;
   age<=0;samples<=0;bias_sum<=0;turn_ticks<=0;wait_ticks<=0;turn_origin<=0;end
  else if(button_start) begin
   armed<=0;age<=0;samples<=0;bias_sum<=0;turn_ticks<=0;wait_ticks<=0;
   if(state==IDLE || state==FAULT) begin state<=CALIBRATE;calibrated<=0;faults<=0;end
   else state<=IDLE;
  end else if(running && (!sensors_ok || encoder_fault || cpu_fault || !cpu_alive || tilt_bad)) begin
   armed<=0;state<=FAULT;
   if(!imu_valid || !gyro_valid || !tilt_valid || tilt_bad) faults[0]<=1;
   if(!lidar_valid || !scan_valid) faults[1]<=1;
   if(encoder_fault) faults[2]<=1;
   if(cpu_fault || !cpu_alive) faults[3]<=1;
  end else begin
   if(state==CALIBRATE) begin
    if(ms_tick && age<10000) age<=age+1'b1;
    if(cpu_fault) begin state<=FAULT;faults[3]<=1;end
    else if(age>=10000 || GEOMETRY_VERIFIED==0) begin
     state<=FAULT;faults[4]<=1;
     if(GEOMETRY_VERIFIED==0) faults[6]<=1;
     if(!calibrated || !imu_valid || !gyro_valid || !tilt_valid || tilt_bad) faults[0]<=1;
     if(!lidar_valid || !scan_valid) faults[1]<=1;
     if(encoder_fault) faults[2]<=1;
     if(!cpu_alive) faults[3]<=1;
    end
    else if(!imu_valid || !gyro_valid || !stationary || !wheels_stationary || raw_gz>82 || raw_gz < -82) begin
     samples<=0;bias_sum<=0;calibrated<=0;
    end else if(gyro_update && !calibrated) begin
     if(samples==63) begin bias<=($signed(bias_sum)+$signed(raw_gz))/64;calibrated<=1;end
     else begin samples<=samples+1'b1;bias_sum<=bias_sum+raw_gz;end
    end
    if(calibrated && stationary && wheels_stationary && sensors_ok && cpu_alive && !cpu_fault &&
       !encoder_fault && !tilt_bad && age<10000 && GEOMETRY_VERIFIED!=0) begin
     armed<=1;state<=FORWARD;age<=0;
    end
   end
   if(running && tick) case(state)
    FORWARD:if(front<=STOP_MM) begin state<=BLOCKED;wait_ticks<=0;end
    BLOCKED:begin
     if(wait_ticks<9) wait_ticks<=wait_ticks+1'b1;
     else if(front>=CLEAR_MM && front!=65535) state<=FORWARD;
     else if(can_left && (!can_right || left>=right)) begin
      state<=LEFT;turn_origin<=yaw;turn_ticks<=0;
     end else if(can_right) begin state<=RIGHT;turn_origin<=yaw;turn_ticks<=0;end
     // Both directions blocked is an ordinary stationary wait, not a fault.
    end
    LEFT,RIGHT:begin
     if(!direction_clear) begin state<=BLOCKED;wait_ticks<=0;end
     else if(turn_reached) begin state<=SETTLE;wait_ticks<=0;end
     else if(turn_ticks>=449 || turn_progress < -17'sd2731) begin
      state<=FAULT;armed<=0;faults[7]<=1;
     end else turn_ticks<=turn_ticks+1'b1;
    end
    SETTLE:begin
     if(wait_ticks<14) wait_ticks<=wait_ticks+1'b1;
     else begin
      wait_ticks<=0;
      if(front>=CLEAR_MM && front!=65535) state<=FORWARD;
      else state<=BLOCKED;
     end
    end
    default:begin end
   endcase
  end
endmodule
`default_nettype wire
