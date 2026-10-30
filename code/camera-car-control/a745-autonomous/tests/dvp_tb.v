`timescale 1ns/1ps
module dvp_tb;
 reg pclk=0;always #5 pclk=~pclk;
 reg rst_n=0,enable=0,vsync=1,href=0;reg [7:0] data=0;
 wire pixel_valid,frame_start,frame_end,frame_good,frame_error;wire [15:0] pixel;
 a745_dvp_capture #(.WIDTH(4),.HEIGHT(2),.SKIP_FRAMES(0)) dut(.*);
 integer seen=0,good=0,starts=0;reg checking=0;
 always @(posedge pclk) begin
  if(frame_start) begin seen=0;starts=starts+1;end
  if(pixel_valid && checking) begin
   if(pixel!==16'h4000+seen) $fatal(1,"DVP byte alignment %h at %0d",pixel,seen);
   seen=seen+1;
  end
  if(frame_end && frame_good) begin if(seen!=8) $fatal(1,"pixel count");good=good+1;end
 end
 task clock_step;begin @(negedge pclk);end endtask
 task image(input immediate_first,input immediate_last);
  integer y,x;reg [15:0] p;
  begin
   vsync=1;href=0;repeat(5) clock_step;
   checking=1;vsync=0;
   if(!immediate_first) repeat(3) clock_step;
   for(y=0;y<2;y=y+1) begin
    for(x=0;x<4;x=x+1) begin
     href=1;p=16'h4000+y*4+x;data=p[15:8];clock_step;data=p[7:0];clock_step;
    end
    href=0;
    if(y==1 && immediate_last) vsync=1;
    repeat(3) clock_step;
   end
   vsync=1;repeat(5) clock_step;checking=0;
  end
 endtask
 initial begin
  repeat(4) clock_step;rst_n=1;enable=1;
  image(0,0);image(1,1);
  if(good!=2) $fatal(1,"legal coincident frame edges rejected %0d",good);
  enable=0;vsync=0;href=1;repeat(5) clock_step;enable=1;repeat(5) clock_step;
  if(frame_start || dut.active) $fatal(1,"enable in middle of frame fabricated a frame start");
  href=0;image(0,1);
  if(good!=3) $fatal(1,"did not recover after enable/reset");
  $display("PASS registered DVP RGB565, coincident first/last frame edges, no fabricated mid-frame startup, recovery");$finish;
 end
 initial begin #20000;$fatal(1,"DVP watchdog");end
endmodule
