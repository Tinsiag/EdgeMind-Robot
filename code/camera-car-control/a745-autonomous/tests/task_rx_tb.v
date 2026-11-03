`timescale 1ns/1ps
module task_rx_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,valid=0,last=0,user=0,session_valid=0;
 reg [7:0] data=0;reg [31:0] session_id=123,video_frame=100;
 wire ready,fresh;wire [2:0] action;wire [7:0] accepted;wire [31:0] config_id,last_sequence;
 a745_task_rx dut(.*);
 reg [7:0] p[0:89];integer i,s,seq=1;
 task checksum;begin
  p[46]=seq;p[47]=seq>>8;p[48]=seq>>16;p[49]=seq>>24;
  p[40]=0;p[41]=0;s='h18166+56;
  for(i=34;i<90;i=i+2)s=s+(p[i]*256+p[i+1]);
  s=(s&65535)+(s>>16);s=(s&65535)+(s>>16);s=(~s)&65535;if(s==0)s=65535;
  p[40]=s>>8;p[41]=s;
 end endtask
 task send(input integer expected);integer before_count;begin
  before_count=accepted;
  for(i=0;i<90;i=i+1)begin @(negedge clk);while(!ready)@(negedge clk);data=p[i];valid=1;last=i==89;end
  @(negedge clk);valid=0;last=0;user=0;repeat(8)@(negedge clk);
  if(accepted!=before_count+expected)$fatal(1,"task accept seq=%0d expected=%0d got=%0d",seq,expected,accepted-before_count);
 end endtask
 task ms;begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end endtask
 initial begin
  $readmemh("tests/task_packet.hex",p);repeat(4)@(negedge clk);rst_n=1;
  send(0);session_valid=1;send(1);if(!fresh || action!=1)$fatal(1,"valid command");
  // Even checksum-correct display-port traffic cannot become a task intent.
  seq=2;p[35]=8'hd9;p[37]=8'hd9;checksum;send(0);
  p[35]=8'hda;p[37]=8'hda;p[43]=8'h44;checksum;send(0);p[43]=8'h54;
  send(0);seq=2;checksum;user=1;send(0);send(1);
  seq=3;p[50]=122;checksum;send(0);p[50]=123;
  p[54]=0;checksum;send(0);p[54]=100;
  p[64]=0;checksum;send(0);p[64]=3;
  p[65]=100;checksum;send(0);p[65]=220;
  p[68]=50;p[69]=0;checksum;send(0);p[68]=232;p[69]=3;
  // Changing config requires STOP before any new moving command.
  p[58]=2;checksum;send(0);p[62]=0;checksum;send(1);
  seq=4;p[62]=1;checksum;send(1);
  repeat(401)ms;if(fresh)$fatal(1,"TTL did not expire");
  video_frame=130;seq=5;checksum;send(0);
  p[62]=0;checksum;send(0);if(fresh)$fatal(1,"lost session was renewed remotely");
  session_valid=0;#1;if(fresh)$fatal(1,"local stop not immediate");repeat(3)@(negedge clk);
  session_valid=1;session_id=124;send(0);
  $display("PASS ET10 checksum/FCS indication, local session, class/score/range, source frame age, config STOP, TTL and replay rejection");$finish;
 end
endmodule
