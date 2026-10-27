`timescale 1ns/1ps
module tft480_panel_tb;
 reg clk=0;always #10 clk=~clk;reg rst_n=0;
 wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl,pixel_request,frame_blank,active;
 wire [10:0] x,y;wire [15:0] tft_rgb;wire [15:0] rgb={x[7:0],y[7:0]};
 a741_tft480_panel #(.BACKLIGHT_FRAMES(1)) dut(.*);
 integer pixels=0,requests=0,frames=0;reg [15:0] launched;
 always @(posedge clk) if(rst_n) begin
  if(pixel_request) begin launched=rgb;requests=requests+1;end
  if(frame_blank) begin
   if(requests!=480*272) $fatal(1,"pixel request count %0d",requests);
   requests=0;frames=frames+1;
  end
 end
 always @(negedge tft_clk) if(rst_n && tft_de) begin
  if(tft_rgb!==launched) $fatal(1,"TFT pixel/request alignment");pixels=pixels+1;
  if(pixels==2*480*272) begin
   if(frames<1 || !tft_bl) $fatal(1,"frame/backlight");
   $display("PASS TFT: two full RGB frames, pixel request/launch alignment, steady backlight");$finish;
  end
 end
 initial begin #50;rst_n=1;end
 initial begin #65000000;$fatal(1,"TFT stream watchdog");end
endmodule
