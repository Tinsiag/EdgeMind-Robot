`timescale 1ns/1ps
// Unmodified official ACG720 HW_TFT50. Compare scan signals with the explicit
// two-pixel OSD delay. Pixel content/alignment is checked by camera_tft800_tb.
module tft800_reference_tb;
 reg clk=0,rst_n=0;always #15.151515 clk=~clk;
 wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;
 wire [15:0] tft_rgb;
 a741_tft800_panel panel(.clk(clk),.rst_n(rst_n),.rgb(16'h5aa5),
  .tft_clk(tft_clk),.tft_de(tft_de),.tft_hsync(tft_hsync),.tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
 wire ref_de,ref_hs,ref_vs;wire [11:0] ref_x,ref_y;
 disp_driver official(.ClkDisp(clk),.Rst_p(!rst_n),.Data(16'h5aa5),.DataReq(),
  .H_Addr(ref_x),.V_Addr(ref_y),.Disp_DE(ref_de),.Disp_HS(ref_hs),.Disp_VS(ref_vs),
  .Disp_Red(),.Disp_Green(),.Disp_Blue(),.Disp_PCLK(),.Frame_Begin());
 reg [2:0] ref0,ref1;
 integer cycles=0,pixels=0,frames=0;
 realtime last_launch=0,last_sample=0,last_data=0;
 always @(posedge clk) if(rst_n) begin
  ref0<={ref_de,ref_hs,ref_vs};ref1<=ref0;
  cycles<=cycles+1;last_launch=$realtime;
  #0.001;
  if(cycles>3 && {tft_de,tft_hsync,tft_vsync}!==ref1)
   $fatal(1,"ACG720 scan mismatch at %d",cycles);
 end
 always @(tft_de or tft_hsync or tft_vsync or tft_rgb) if(rst_n) begin
  if(tft_clk!==0) $fatal(1,"800 data must launch on falling PCLK");
  if(last_sample && $realtime-last_sample<15.15) $fatal(1,"800 hold below half-cycle");
  last_data=$realtime;
 end
 always @(posedge tft_clk) if(rst_n) begin
  if(last_sample && ($realtime-last_sample<30.30 || $realtime-last_sample>30.31)) $fatal(1,"PCLK not fixed33MHz");
  if(last_launch && $realtime-last_launch<15.15) $fatal(1,"short high/low pulse");
  if(last_data && $realtime-last_data<15.15) $fatal(1,"800 setup below half-cycle");
  last_sample=$realtime;
  if(tft_de) begin pixels=pixels+1;if(tft_rgb!==16'h5aa5) $fatal(1,"active RGB");end
  else if(tft_rgb!==0) $fatal(1,"blank RGB");
  if(cycles==13*1056*525) begin
   if(pixels!=13*800*480 || !tft_bl) $fatal(1,"missing pixels/backlight %d",pixels);
   $display("PASS ACG720800 scan,13 complete frames,33MHz fixed clock,rising-edge sample/half-cycle setup hold,200ms backlight");$finish;
  end
 end
 initial begin #1;rst_n=1;#1;rst_n=0;#50;rst_n=1;end
 initial begin #230000000;$fatal(1,"800 reference watchdog");end
endmodule
