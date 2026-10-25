`timescale 1ns/1ps
module clock_audit(input wire clk,stop_n,
 output wire tmds_clk_p,tmds_clk_n,
 output wire [2:0] tmds_data_p,tmds_data_n);
 wire serial_clk,pixel_clk,locked;
 A741_Video_PLL video_pll(.clkin(clk),.clkout0(),.clkout1(serial_clk),
  .lock(locked),.mdclk(clk),.reset(!stop_n));
 CLKDIV pixel_divider(.HCLKIN(serial_clk),.RESETN(locked),
  .CLKOUT(pixel_clk),.CALIB(1'b1));
 defparam pixel_divider.DIV_MODE="5";
 a741_hdmi hdmi(.pixel_clk(pixel_clk),.serial_clk(serial_clk),
  .rst_n(stop_n && locked),.rgb(16'hf800),.de(1'b1),.hsync(1'b0),.vsync(1'b0),
  .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
  .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
endmodule
