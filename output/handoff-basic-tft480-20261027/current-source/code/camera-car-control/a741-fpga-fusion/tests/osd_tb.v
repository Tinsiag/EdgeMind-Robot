`timescale 1ns/1ps
module osd_tb;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0,frame_blank=0,de=1,status_update=0,pixel_valid=1;
 reg [10:0] x=0,y=100;reg [15:0] pixel=16'hf800;
 reg [895:0] status_snapshot=0;reg [255:0] fusion_snapshot=0;
 wire [15:0] rgb;a741_osd dut(.*);
 integer age,i,j,white=0;
 task publish;begin @(negedge clk);status_update=1;@(negedge clk);status_update=0;end endtask
 task prepared;begin age=0;while(dut.state!=dut.READY && age<200) begin @(negedge clk);age=age+1;end
  if(age>=200) $fatal(1,"overlay conversion latency");end endtask
 task commit;begin @(negedge clk);frame_blank=1;@(negedge clk);frame_blank=0;end endtask
 initial begin
  #50;rst_n=1;status_snapshot[160]=1;status_snapshot[163]=1;status_snapshot[165]=1;
  status_snapshot[431:416]=-16'sd16384;status_snapshot[479:464]=345;
  status_snapshot[495:480]=65535;status_snapshot[511:496]=900;status_snapshot[207:192]=1024;
  fusion_snapshot[47:32]=-16'sd32768;fusion_snapshot[63:48]=16'd32767;
  fusion_snapshot[64]=1;fusion_snapshot[15:8]=2;fusion_snapshot[201]=1;
  publish();commit();if(dut.lines[0]!={32{8'h20}}) $fatal(1,"partial text escaped staging");
  prepared();if(dut.lines[0]!={32{8'h20}}) $fatal(1,"text published before blank");commit();
  if(dut.lines[0][255-5*8-:48]!="-180.0" || dut.lines[0][255-18*8-:48]!=" 179.9") $fatal(1,"roll/pitch signed extrema");
  if(dut.lines[1][255-4*8-:48]!="-090.0" || dut.lines[1][255-24*8-:40]!="LEFT ") $fatal(1,"yaw/avoidance text");
  if(dut.lines[2][255-2*8-:48]!=" 00345" || dut.lines[2][255-11*8-:48]!="INVAL ") $fatal(1,"lidar validity");
  if(dut.lines[3][255-22*8-:48]!=" 01024") $fatal(1,"fault text");
  for(j=8;j<24;j=j+1) for(i=48;i<432;i=i+1) begin
   @(negedge clk);x=i;y=j;repeat(3) @(negedge clk);
   if(rgb==16'hffff) white=white+1;else if(rgb!=16'h0022) $fatal(1,"overlay glyph/background");
  end
  if(white<100) $fatal(1,"no text pixels");
  @(negedge clk);x=100;y=100;repeat(3) @(negedge clk);
  if(rgb!=16'hf800) $fatal(1,"camera passthrough");
  status_snapshot[160]=0;fusion_snapshot[64]=0;status_snapshot[163]=0;publish();prepared();
  if(dut.lines[0][255-5*8-:48]!="-180.0") $fatal(1,"status tore active frame");commit();
  if(dut.lines[0][255-5*8-:48]!="STALE " || dut.lines[2][255-2*8-:48]!="INVAL ") $fatal(1,"stale sensors shown valid");
  publish();repeat(10) @(negedge clk);rst_n=0;@(negedge clk);rst_n=1;commit();
  if(dut.lines[0]!={32{8'h20}}) $fatal(1,"reset exposed old work buffer");
  $display("PASS compact overlay: coherent roll/pitch/yaw, signed extrema, stale validity, lidar/faults, passthrough/reset");$finish;
 end
 initial begin #3000000;$fatal(1,"OSD watchdog");end
endmodule
