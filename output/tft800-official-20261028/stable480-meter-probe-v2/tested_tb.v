`timescale 1ns/1ps
module Gowin_PLL(input clkin,mdclk,reset,output reg clkout0=0,output lock);
 always #55.555556 clkout0=~clkout0;
 assign lock=!reset;
endmodule
module stable480_meter_tb;
 reg clk50M=0,reset_n=0;always #10 clk50M=~clk50M;
 wire [15:0] TFT_rgb;wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm;
 wire [7:0] led;wire left_in1,left_in2,right_in1,right_in2;
 GSR GSR(.GSRI(1'b1));
 // Shorten only the meter's measurement window; real scan/clock/pad logic.
 official_probe #(.WINDOW_CYCLES(1000000)) dut(.*);
 integer x=0,y=0,k,index,frame_count=0,colors[0:7],cycles=0;
 reg was_de=0,was_vs=0,check_pixels=1;
 reg [15:0] expected;realtime changed=0;
 always @(TFT_rgb or TFT_de or TFT_hs or TFT_vs) if(reset_n && $time>200 && check_pixels) begin
  if(TFT_clk!==1) $fatal(1,"output changes at sample edge");
  changed=$realtime;
 end
 always @(negedge TFT_clk) if(reset_n && $time>500 && check_pixels) begin
  if(changed && $realtime-changed<55.55) $fatal(1,"missing setup time");
  if(TFT_pwm!==1 || TFT_de!==dut.pins[18]) $fatal(1,"official fixed mapping");
  if(TFT_vs && !was_vs) begin
   if(frame_count>0 && y!=272) $fatal(1,"active rows %0d",y);
   y=0;frame_count=frame_count+1;
  end
  was_vs=TFT_vs;
  if(TFT_de) begin
   if(!was_de)x=0;
   if(x>3 && x<477 && x%240>3 && y>3 && y<269 && y%68>3) begin
    index=(y/68)*2+(x/240);
    case(index)
     0:expected=0;1:expected=16'h001f;2:expected=16'hf800;3:expected=16'hf81f;
     4:expected=16'h07e0;5:expected=16'h07ff;6:expected=16'hffe0;7:expected=16'hffff;
    endcase
    if(TFT_rgb!==expected)$fatal(1,"pixel %0d,%0d",x,y);
    colors[index]=colors[index]+1;
   end
   x=x+1;
  end else if(was_de)begin
   if(x!=480)$fatal(1,"active pixels %0d",x);
   y=y+1;
  end
  was_de=TFT_de;
 end
 task windows(input integer n);
  integer i;
  begin
   for(i=0;i<n;i=i+1)begin
    @(posedge clk50M);while(dut.window_count!=999999)@(posedge clk50M);
    @(posedge clk50M);#1;
   end
  end
 endtask
 task normal_checks;
  begin
   if(led[7:3]!==5'b11111 || !led[0])
    $fatal(1,"meter failed: led=%b clock=%0d hs=%0d vs=%0d de=%0d samples=%0d mismatch=%b",led,dut.clock_edges,dut.hs_edges,dut.vs_edges,dut.de_edges,dut.de_samples,dut.mismatch_seen);
   if({left_in1,left_in2,right_in1,right_in2}!==0)$fatal(1,"motor lock");
  end
 endtask
 initial begin
  for(k=0;k<8;k=k+1)colors[k]=0;
  #1;reset_n=1;#2;reset_n=0;#53;reset_n=1;
  windows(3);normal_checks();
  for(k=0;k<8;k=k+1)if(colors[k]<1000)$fatal(1,"missing color %0d",k);
  if(frame_count<3)$fatal(1,"not enough whole frames");
  check_pixels=0;
  // Each injected fault must affect its independent monitor, then recover.
  force dut.read_clk=0;windows(2);
  if(led[4] || led[7])$fatal(1,"clock pad fault not detected");
  release dut.read_clk;windows(2);normal_checks();
  force dut.read_de=0;windows(2);
  if(led[5] || led[6] || led[7])$fatal(1,"DE pad fault not detected");
  release dut.read_de;windows(2);normal_checks();
  force dut.read_rgb=16'h0000;windows(2);
  if(led[6] || led[7])$fatal(1,"RGB pad fault not detected");
  release dut.read_rgb;windows(2);normal_checks();
  $display("PASS fixed480x272/9MHz eight-block raster; actual IOBUF sampling; clock/DE/RGB fault detection and recovery; motors low");$finish;
 end
 initial begin #350000000;$fatal(1,"watchdog");end
endmodule
