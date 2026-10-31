`timescale 1ns/1ps
`default_nettype none
// Accelerometer inclination, not a yaw/position estimator:
// roll=atan2(ay,az), pitch=atan2(-ax,hypot(ay,az)). Q15 half-turn units.
// One iterative vectoring CORDIC serves both axes. Its first-pass magnitude
// is corrected by 1/K, avoiding two squarers and a separate square root.
// Linear acceleration can bias inclination; sensor-axis conventions apply.
// Publish the angle pair whose maximum absolute inclination is the median of
// three samples. This rejects one-sample
// acceleration/vibration spikes without changing the 22.5 degree safety limit;
// a sustained tilt reaches the safety logic after two fresh samples.
module a741_attitude(
 input wire clk,rst_n,sample_update,sample_valid,
 input wire signed [15:0] ax,ay,az,
 output reg signed [15:0] roll,pitch,output reg valid,done
);
 localparam IDLE=0,ROLL=1,SCALE=2,PITCH_START=3,PITCH=4;
 reg [2:0] state;reg [3:0] index;
 reg signed [21:0] x,y,ax_q;
 reg signed [16:0] z,angle_step;
 reg signed [15:0] roll_q;reg yz_zero;
 reg signed [15:0] roll_prev,roll_old,pitch_prev,pitch_old;
 reg [1:0] history_count;
 reg [37:0] magnitude_product;
 wire signed [21:0] nx=y>=0 ? x+(y>>>index):x-(y>>>index);
 wire signed [21:0] ny=y>=0 ? y-(x>>>index):y+(x>>>index);
 wire signed [16:0] nz=y>=0 ? z+angle_step:z-angle_step;
 wire signed [21:0] ax_scaled=$signed({{6{ax[15]}},ax})<<<4;
 wire signed [21:0] ay_scaled=$signed({{6{ay[15]}},ay})<<<4;
 wire signed [21:0] az_scaled=$signed({{6{az[15]}},az})<<<4;
 // At +/-2g sensitivity, max axis below 0.25g is inconsistent with static
 // gravity. Reject near-zero/free-fall input rather than showing a valid tilt.
 wire meaningful=(ax>=4096 || ax<=-4096 || ay>=4096 || ay<=-4096 || az>=4096 || az<=-4096);
 function [15:0] excursion;
  input signed [15:0] r,p;
  reg [15:0] ar,ap;
  begin
   ar=r[15] ? (~r+16'd1):r;ap=p[15] ? (~p+16'd1):p;
   excursion=ar>ap ? ar:ap;
  end
 endfunction
 function [31:0] median_pair;
  input signed [15:0] r0,p0,r1,p1,r2,p2;
  reg [15:0] a,b,c;
  begin
   a=excursion(r0,p0);b=excursion(r1,p1);c=excursion(r2,p2);
   // Rank complete pairs by absolute excursion, not signed angles: alternating
   // +179/-179 degrees or roll/pitch axes must never look level at the median.
   if ((a<=b && b<=c) || (c<=b && b<=a)) median_pair={r1,p1};
   else if ((b<=a && a<=c) || (c<=a && a<=b)) median_pair={r0,p0};
   else median_pair={r2,p2};
  end
 endfunction
 always @* case(index)
  0:angle_step=8192;1:angle_step=4836;2:angle_step=2555;3:angle_step=1297;4:angle_step=651;
  5:angle_step=326;6:angle_step=163;7:angle_step=81;8:angle_step=41;9:angle_step=20;
  10:angle_step=10;11:angle_step=5;12:angle_step=3;13:angle_step=1;default:angle_step=1;
 endcase
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   state<=IDLE;index<=0;x<=0;y<=0;z<=0;ax_q<=0;roll_q<=0;yz_zero<=0;
   roll_prev<=0;roll_old<=0;pitch_prev<=0;pitch_old<=0;history_count<=0;
   magnitude_product<=0;roll<=0;pitch<=0;valid<=0;done<=0;
  end else begin
   done<=0;
   if(!sample_valid) begin valid<=0;state<=IDLE;history_count<=0;end
   else if(sample_update) begin
    // Restart with the newest complete triad if an update interrupts work.
    // valid describes the last published roll/pitch pair, not calculator
    // idle/busy. Keep it through a normal update, publishing both angles
    // atomically at completion. Bad gravity or stale input still invalidates
    // immediately, so motion protection does not ignore a real sensor fault.
    if(!meaningful) begin valid<=0;history_count<=0;end
    index<=0;ax_q<=ax_scaled;yz_zero<=ay==0 && az==0;
    x<=az<0 ? -az_scaled:az_scaled;y<=az<0 ? -ay_scaled:ay_scaled;
    z<=az<0 ? (ay>=0 ? 17'sd32768:-17'sd32768):17'sd0;
    state<=meaningful ? ROLL:IDLE;
   end else case(state)
    ROLL:begin
     x<=nx;y<=ny;z<=nz;
     if(index==14) begin roll_q<=yz_zero ? 16'sd0:nz[15:0];state<=SCALE;end
     else index<=index+1'b1;
    end
    SCALE:begin magnitude_product<=$unsigned(x)*16'd19898;state<=PITCH_START;end
    PITCH_START:begin x<=yz_zero ? 22'sd0:$signed(magnitude_product[36:15]);y<=-ax_q;z<=0;index<=0;state<=PITCH;end
    PITCH:begin
     x<=nx;y<=ny;z<=nz;
     if(index==14) begin
      // Keep the raw CORDIC result internal. Publish a median of the current
      // and two preceding complete samples, duplicating the first sample only
      // while the history is filling. A single impulse therefore cannot make
      // the motion interlock see a false over-tilt.
      if(history_count==0) begin
       roll<=roll_q;pitch<=nz[15:0];
      end else if(history_count==1) begin
       {roll,pitch}<=median_pair(roll_prev,pitch_prev,roll_prev,pitch_prev,roll_q,nz[15:0]);
      end else begin
       {roll,pitch}<=median_pair(roll_old,pitch_old,roll_prev,pitch_prev,roll_q,nz[15:0]);
      end
      roll_old<=roll_prev;roll_prev<=roll_q;
      pitch_old<=pitch_prev;pitch_prev<=nz[15:0];
      if(history_count<2) history_count<=history_count+1'b1;
      valid<=1;done<=1;state<=IDLE;
     end
     else index<=index+1'b1;
    end
    default:state<=IDLE;
   endcase
  end
endmodule
`default_nettype wire
