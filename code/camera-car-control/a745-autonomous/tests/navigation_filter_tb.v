`timescale 1ns/1ps
module navigation_filter_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,tick=0,button_start=0,gyro_update=0,point_valid=0;
 reg [15:0] angle=0,distance=2000;reg [7:0] confidence=180;
 wire filtered_valid;wire [15:0] filtered_angle,filtered_distance;wire [7:0] filtered_confidence;
 a745_lidar_filter filter(.clk(clk),.rst_n(rst_n),.stream_valid(1'b1),.*);
 wire scan_valid,left_clear,right_clear;wire [15:0] front,left,right,rear;wire [7:0] scan_sequence;
 a745_navigation_scan scan(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.stream_valid(1'b1),
  .point_valid(filtered_valid),.angle(filtered_angle),.distance(filtered_distance),.confidence(filtered_confidence),
  .scan_valid(scan_valid),.front(front),.left(left),.right(right),.rear(rear),
  .left_clear(left_clear),.right_clear(right_clear),.scan_sequence(scan_sequence));
 wire armed,calibrated,lidar_enabled,motor_enable;wire signed [15:0] bias;
 wire [7:0] state;wire [15:0] faults;wire signed [31:0] target_l,target_r;
 a745_autonomy #(.GEOMETRY_VERIFIED(1)) autonomy(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.tick(tick),
  .button_start(button_start),.gyro_update(gyro_update),.imu_valid(1'b1),.gyro_valid(1'b1),.stationary(1'b1),
  .tilt_valid(1'b1),.raw_gz(16'sd0),.roll(16'sd0),.pitch(16'sd0),.yaw(16'sd0),
  .wheels_stationary(1'b1),.encoder_fault(1'b0),.left_count(32'sd0),.right_count(32'sd0),.rear(16'd350),.cpu_alive(1'b1),.cpu_fault(1'b0),.lidar_valid(1'b1),
  .scan_valid(scan_valid),.front(front),.left(left),.right(right),.left_clear(left_clear),.right_clear(right_clear),
  .armed(armed),.calibrated(calibrated),.bias(bias),.lidar_enabled(lidar_enabled),.motor_enable(motor_enable),
  .state(state),.faults(faults),.target_l(target_l),.target_r(target_r));
 task control_tick;begin @(negedge clk);tick=1;ms_tick=1;@(negedge clk);tick=0;ms_tick=0;end endtask
 task scene(input integer which);
  integer i,b,d,c;
  begin
   for(i=0;i<360;i=i+1) begin
    b=(27000-i*100+36000)%36000;d=2000;c=180;
    if(b<=3000 || b>=33000) d=which==0 ? 1500:which==1 ? 299:301;
    if(b>=4500 && b<=13500) d=700;
    if(b>=22500 && b<=31500) d=711;
    if(which!=0 && b>=8900 && b<=9100) begin d=which==1 ? 106:250;c=70;end
    if(which==3 && b>=26900 && b<=27100) begin d=250;c=70;end
    // A repeatable weak outlier in an otherwise clear path must not lock turns.
    if(b==1000) begin d=42;c=48;end
    @(negedge clk);point_valid=1;angle=16'(i*100);distance=16'(d);confidence=8'(c);
   end
   @(negedge clk);point_valid=0;repeat(8) @(negedge clk);
  end
 endtask
 initial begin
  repeat(4) @(negedge clk);rst_n=1;scene(0);scene(0);scene(0);
  if(!scan_valid || front!=1500 || !left_clear || !right_clear) $fatal(1,"weak outlier corrupted scan");
  button_start=1;@(negedge clk);button_start=0;
  repeat(64) begin gyro_update=1;@(negedge clk);gyro_update=0;@(negedge clk);end
  repeat(4) @(negedge clk);
  if(state!=2 || !motor_enable) $fatal(1,"integration start failed");
  scene(1);scene(1);scene(1);repeat(12) control_tick;
  if(state!=5 || motor_enable || faults || left!=106 || right!=711 || left_clear || right_clear)
   $fatal(1,"photo-like close left obstacle must block both swept envelopes");
  scene(2);scene(2);scene(2);repeat(12) control_tick;
  if(front!=301 || left!=250 || right!=711 || !right_clear || state!=4 || target_l<=0 || target_r>=0)
   $fatal(1,"safe right path did not escape BLOCK above 300mm");
  scene(3);scene(3);scene(3);repeat(12) control_tick;
  if(state!=5 || motor_enable || faults || right_clear) $fatal(1,"real weak coherent obstacle was ignored");
  button_start=1;@(negedge clk);button_start=0;repeat(3) @(negedge clk);
  if(state!=0 || motor_enable || armed) $fatal(1,"S1 stop integration failed");
  $display("PASS measured-noise integration, photo 106mm both blocked, 301/250/711 right selection, real obstacle revocation and S1 stop");$finish;
 end
 initial begin #200000;$fatal(1,"filtered navigation watchdog");end
endmodule
