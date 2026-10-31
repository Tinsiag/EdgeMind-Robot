`timescale 1ns/1ps
module lidar_filter_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,stream_valid=1,point_valid=0;
 reg [15:0] angle=0,distance=0;reg [7:0] confidence=0;
 wire filtered_valid;wire [15:0] filtered_angle,filtered_distance;wire [7:0] filtered_confidence;
 a745_lidar_filter dut(.*);
 integer sent=0,received=0;
 reg [15:0] expected_angle[0:63],expected_distance[0:63];reg [7:0] expected_confidence[0:63];
 task sample(input integer a,input integer d,input integer c,input integer keep);
  begin
   @(negedge clk);point_valid=1;angle=16'(a);distance=16'(d);confidence=8'(c);
   expected_angle[sent]=16'(a);expected_distance[sent]=16'(d);expected_confidence[sent]=keep ? 8'(c):0;sent=sent+1;
  end
 endtask
 always @(posedge clk) begin
  #1;if(filtered_valid) begin
   if(filtered_angle!==expected_angle[received] || filtered_distance!==expected_distance[received] ||
      filtered_confidence!==expected_confidence[received])
    $fatal(1,"sample %0d: got %0d/%0d/%0d expected %0d/%0d/%0d",received,
     filtered_angle,filtered_distance,filtered_confidence,expected_angle[received],expected_distance[received],expected_confidence[received]);
   received=received+1;
  end
 end
 initial begin
  repeat(4) @(negedge clk);rst_n=1;
  // Raw measured failure pattern: isolated/pair weak near returns among walls.
  sample(100,2000,200,0);sample(180,48,61,0);sample(260,2000,200,0);
  sample(340,100,48,0);sample(420,101,51,0);sample(500,2000,200,0);
  // Preserve all three members and both endpoints of weak coherent objects.
  sample(580,500,70,1);sample(660,510,70,1);sample(740,520,70,1);
  sample(820,2000,200,0);
  // A strong single tiny obstacle must remain visible, no minimum range cut.
  sample(900,22,220,1);sample(980,2000,200,0);
  // Different near ranges do not create a cluster merely by being adjacent.
  sample(1060,30,50,0);sample(1140,100,50,0);sample(1220,200,50,0);
  sample(1300,5000,20,1);
  // Missing sectors, invalid returns and low confidence break adjacency.
  sample(2000,500,100,0);sample(3000,500,100,0);sample(4000,500,100,0);
  sample(4080,0,220,0);sample(4160,500,100,0);sample(4240,500,19,0);sample(4320,500,100,0);
  // Three adjacent samples across raw-angle/packet boundaries still qualify.
  sample(35900,150,50,1);sample(35980,151,50,1);sample(60,152,50,1);
  sample(140,0,0,0);sample(220,0,0,0);
  @(negedge clk);point_valid=0;repeat(5) @(negedge clk);
  if(received!=sent-2) $fatal(1,"lookahead lost samples");
  stream_valid=0;repeat(3) @(negedge clk);stream_valid=1;sent=0;received=0;
  sample(100,500,100,0);sample(180,0,0,0);sample(260,0,0,0);
  @(negedge clk);point_valid=0;repeat(3) @(negedge clk);
  if(received!=1) $fatal(1,"stream-loss history reused");
  $display("PASS LD06 weak singleton/pair rejection, coherent triple endpoints, strong tiny obstacle, gaps, confidence, wrap and stream loss");$finish;
 end
 initial begin #100000;$fatal(1,"LD06 filter watchdog");end
endmodule
