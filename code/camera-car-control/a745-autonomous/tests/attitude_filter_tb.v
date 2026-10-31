`timescale 1ns/1ps
module attitude_filter_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,sample_update=0,sample_valid=1;
 reg signed [15:0] ax=0,ay=0,az=16384;
 wire signed [15:0] roll,pitch;wire valid,done;
 a741_attitude dut(.*);
 integer updates=0,commits=0;
 always @(negedge clk) if(done) commits=commits+1;
 function unsafe(input signed [15:0] r,p);
  begin unsafe=r>4096 || r< -4096 || p>4096 || p< -4096;end
 endfunction
 task sample(input integer x,y,z);
  integer before_commit;
  begin
   @(negedge clk);ax=16'(x);ay=16'(y);az=16'(z);sample_update=1;
   before_commit=commits;updates=updates+1;
   @(negedge clk);sample_update=0;
   repeat(60) @(negedge clk);
   if(commits!=before_commit+1 || !valid) $fatal(1,"fresh meaningful sample was not published once");
  end
 endtask
 task level;
  begin repeat(3) sample(0,0,16384);
   if(unsafe(roll,pitch)) $fatal(1,"level history not recovered");end
 endtask
 task isolated(input integer x,y,z);
  begin
   level();sample(x,y,z);
   if(unsafe(roll,pitch)) $fatal(1,"isolated acceleration spike leaked to interlock: %d/%d",roll,pitch);
   sample(0,0,16384);
   if(unsafe(roll,pitch)) $fatal(1,"spike leaked on recovery");
   sample(0,0,16384);
   if(unsafe(roll,pitch)) $fatal(1,"spike leaked after recovery");
  end
 endtask
 task sustained(input integer x,y,z);
  real expected_roll,expected_pitch;
  begin
   level();sample(x,y,z);
   sample(x,y,z);
   if(!unsafe(roll,pitch)) $fatal(1,"sustained true tilt delayed beyond second sample");
   expected_roll=$atan2($itor(y),$itor(z))*32768.0/3.141592653589793;
   expected_pitch=$atan2(-$itor(x),$sqrt($itor(y)*$itor(y)+$itor(z)*$itor(z)))*32768.0/3.141592653589793;
   if($abs($itor(roll)-expected_roll)>8.0 || $abs($itor(pitch)-expected_pitch)>8.0)
    $fatal(1,"filtered steady angle differs from analytic gravity angle: %d/%d",roll,pitch);
  end
 endtask
 initial begin
  repeat(4) @(negedge clk);rst_n=1;
  // A tilted startup is never seeded with a fictitious level sample.
  sample(0,8192,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"tilted startup was hidden");
  isolated(0,8700,16384); // approximately the recorded 27.96 degree roll
  isolated(0,-8700,16384);
  isolated(8700,0,16384);isolated(-8700,0,16384);
  isolated(0,32767,1000);isolated(0,-32768,1000);
  sustained(0,8192,14189);sustained(0,-8192,14189);
  sustained(-8192,0,14189);sustained(8192,0,14189);
  // Two dangerous samples must stop even if their signs or axes differ.
  level();sample(0,200,-16384);sample(0,-200,-16384);
  if(!unsafe(roll,pitch)) $fatal(1,"+/-180 roll wrap masked inversion");
  level();sample(0,8192,14189);sample(-8192,0,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"independent-axis filtering masked sustained tilt");
  level();sample(0,8192,14189);sample(0,-8192,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"opposite roll signs masked sustained tilt");
  // Two dangerous samples in a three-sample window are deliberately retained.
  level();sample(0,8192,14189);sample(0,0,16384);sample(0,8192,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"recurring dangerous samples were hidden");
  // Normal under-limit motion retains the existing numerical threshold.
  level();repeat(4) sample(0,6100,15160); // about 21.9 degrees
  if(unsafe(roll,pitch)) $fatal(1,"under-limit angle stopped motion");
  repeat(2) sample(0,6400,15080); // about 23 degrees
  if(!unsafe(roll,pitch)) $fatal(1,"22.5 degree threshold was raised");
  // Sample arrival does not clear valid while the CORDIC is working.
  level();@(negedge clk);sample_update=1;
  @(negedge clk);sample_update=0;
  repeat(40) begin @(negedge clk);if(!valid) $fatal(1,"normal calculation interrupted valid");end
  // Invalid input still invalidates immediately and flushes history.
  @(negedge clk);ax=0;ay=0;az=0;sample_update=1;
  @(negedge clk);sample_update=0;
  if(valid) $fatal(1,"free-fall input was hidden by filter");
  sample(0,8192,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"old level history survived invalid gravity");
  sample_valid=0;repeat(2) @(negedge clk);
  if(valid) $fatal(1,"stale/bus-invalid sample was hidden by filter");
  sample_valid=1;sample(0,-8192,14189);
  if(!unsafe(roll,pitch)) $fatal(1,"old history survived bus invalidation");
  $display("PASS inclination median: isolated +/-roll/pitch shocks rejected; 2-of-3 overtilt retained across signs/axes/wrap; true tilt confirmed on second consecutive sample; invalid/stale fail-closed");$finish;
 end
 initial begin #2000000;$fatal(1,"attitude filter watchdog");end
endmodule
