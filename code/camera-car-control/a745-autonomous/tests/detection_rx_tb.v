`timescale 1ns/1ps
module detection_rx_tb;
 reg clk=0;always #4 clk=~clk;
 reg rst_n=0,valid=0,last=0,user=0;reg [7:0] data=0;
 wire ready,update;wire [771:0] detections;wire [7:0] accepted;
 a745_detection_rx #(.SESSION_CYCLES(2000)) dut(.*,.update_ready(1'b1));
 reg [7:0] p[0:159];integer n,i,k,s,checks=0;reg [31:0] seq=10;
 task make_packet(input integer count);
 begin
  for(i=0;i<160;i=i+1)p[i]=0;
  p[0]=2;p[5]=2;p[6]='h48;p[7]='hda;p[8]='h35;p[9]='h60;p[11]='h99;
  p[12]=8;p[14]='h45;p[17]=44+count*12;p[22]=64;p[23]=17;
  p[26]=192;p[27]=168;p[29]=3;p[30]=192;p[31]=168;p[33]=2;
  p[34]='h17;p[35]='hd9;p[36]='h17;p[37]='hd9;p[39]=24+count*12;
  p[42]="E";p[43]="D";p[44]="1";p[45]="0";
  p[46]=seq;p[47]=seq>>8;p[48]=seq>>16;p[49]=seq>>24;
  p[50]=count;p[52]='h80;p[53]=2;p[54]='he0;p[55]=1;
  for(k=0;k<count;k=k+1) begin
   p[58+k*12]=10+k;p[60+k*12]=20;p[62+k*12]=100;p[64+k*12]=200;p[67+k*12]=200;
  end
  n=(count==0)?60:58+12*count;
  checksum;
 end endtask
 task checksum;
 begin
  p[24]=0;p[25]=0;s=0;
  for(i=14;i<34;i=i+2)s=s+(p[i]*256+p[i+1]);
  s=(s&65535)+(s>>16);s=(s&65535)+(s>>16);s=(~s)&65535;p[24]=s>>8;p[25]=s;
  p[40]=0;p[41]=0;s='h18166+p[39];
  for(i=34;i<34+p[39];i=i+2)s=s+(p[i]*256+p[i+1]);
  s=(s&65535)+(s>>16);s=(s&65535)+(s>>16);s=(~s)&65535;if(s==0)s=65535;
  p[40]=s>>8;p[41]=s;
 end endtask
 task send_packet(input integer expected);
 integer before_count;
 begin
  before_count=accepted;
  for(i=0;i<n;i=i+1)begin
   @(negedge clk);while(!ready)@(negedge clk);
   valid=1;data=p[i];last=i==n-1;
  end
  @(negedge clk);valid=0;last=0;user=0;
  repeat(140)@(negedge clk);
  if(accepted!=((before_count+expected)&255))$fatal(1,"accept mismatch count=%d expected delta=%d state=%d",accepted,expected,dut.state);
  checks=checks+1;
 end endtask
 initial begin
  repeat(4)@(negedge clk);rst_n=1;
  make_packet(1);send_packet(1);
  if(detections[3:0]!=1 || detections[4+:16]!=10 || detections[52+:16]!=200)$fatal(1,"box decode");
  send_packet(0);seq=9;make_packet(1);send_packet(0);
  seq=11;make_packet(8);send_packet(1);
  if(detections[3:0]!=8 || detections[676+:16]!=17)$fatal(1,"eight boxes");
  seq=12;make_packet(0);send_packet(1);if(detections!=0)$fatal(1,"clear");
  seq=13;make_packet(1);p[0]=3;send_packet(0);
  make_packet(1);p[24]=p[24]^1;send_packet(0);
  make_packet(1);p[67]=p[67]^1;send_packet(0);
  make_packet(1);p[40]=0;p[41]=0;send_packet(0);
  make_packet(1);p[21]=1;checksum;send_packet(0);
  make_packet(1);p[51]=1;checksum;send_packet(0);
  make_packet(1);p[58]=150;checksum;send_packet(0);
  make_packet(1);p[66]=80;checksum;send_packet(0);
  make_packet(1);p[68]=1;checksum;send_packet(0);
  make_packet(1);n=n-1;send_packet(0);
  make_packet(1);n=n+1;send_packet(0);
  make_packet(1);user=1;send_packet(0);
  repeat(2100)@(negedge clk);seq=1;make_packet(1);send_packet(1);
  $display("PASS detection parser %0d valid/malformed/sequence/session cases",checks);$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
