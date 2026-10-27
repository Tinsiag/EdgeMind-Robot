`timescale 1ns/1ps
module attitude_tb;
 reg clk=0;always #10 clk=~clk;reg rst_n=0,sample_update=0,sample_valid=1;
 reg signed [15:0] ax=0,ay=0,az=0;wire signed [15:0] roll,pitch;wire valid,done;
 a741_attitude dut(.*);
 reg [79:0] vectors[0:2047];integer i,age,er,ep,worst=0;
 reg signed [15:0] wrapped_error;
 task sample(input signed [15:0] sx,sy,sz);
  begin @(negedge clk);ax=sx;ay=sy;az=sz;sample_update=1;@(negedge clk);sample_update=0;end
 endtask
 task await_result;
  begin age=0;while(!done && age<40) begin @(negedge clk);age=age+1;end
   if(!done || !valid || age>=40) $fatal(1,"inclination latency/valid");end
 endtask
 initial begin
  $readmemh("tests/attitude-vectors.hex",vectors);
  #50;rst_n=1;
  for(i=0;i<2048;i=i+1) begin
   sample(vectors[i][79:64],vectors[i][63:48],vectors[i][47:32]);await_result();
   wrapped_error=roll-$signed(vectors[i][31:16]);er=wrapped_error;
   wrapped_error=pitch-$signed(vectors[i][15:0]);ep=wrapped_error;
   if(er<0) er=-er;if(ep<0) ep=-ep;
   if(er>worst) worst=er;if(ep>worst) worst=ep;
   if(er>8 || ep>8) $fatal(1,"atan2/hypot mismatch vector%0d a=%0d/%0d/%0d roll=%0d pitch=%0d error=%0d/%0d",i,ax,ay,az,roll,pitch,er,ep);
  end
  sample(0,0,0);repeat(40) @(negedge clk);if(valid || done) $fatal(1,"free-fall/zero vector shown valid");
  sample(0,16384,0);repeat(5) @(negedge clk);sample(0,0,16384);await_result();
  if(roll>8 || roll<-8 || pitch>8 || pitch<-8) $fatal(1,"newest sample did not replace interrupted conversion");
  sample(8192,8192,8192);repeat(5) @(negedge clk);sample_valid=0;repeat(40) @(negedge clk);
  if(valid || done) $fatal(1,"stale sensor published an angle");
  $display("PASS inclination: 2048 independent atan2/hypot vectors, quadrants/extrema, <=8 Q15 LSB error (worst %0d), bounded latency, zero/stale and interrupted updates",worst);$finish;
 end
 initial begin #3000000;$fatal(1,"inclination watchdog");end
endmodule
