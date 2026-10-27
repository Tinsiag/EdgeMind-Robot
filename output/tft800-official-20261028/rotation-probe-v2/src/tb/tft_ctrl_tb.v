/////////////////////////////////////////////////////////////////////////////////
// Company: 武汉芯路恒科技有限公司
// Engineer: 小梅哥团队
// Web: www.corecourse.cn
// 
// Create Date: 2020/07/20 00:00:00
// Design Name: tft_ctrl_test
// Module Name: tft_ctrl_tb
// Project Name: tft_ctrl_test
// Target Devices: XC7A35T-2FGG484I
// Tool Versions: Vivado 2018.3
// Description: tft_ctrl模块仿真文件
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
`timescale 1ns / 1ns
`define CLK_PERIOD 30

module tft_ctrl_tb();

  reg clk50M;
  reg reset_n;

  
  reg[15:0]TFT_rgb;
  wire DataReq;
  wire reset;
  wire [11:0] visible_hcount;
  wire [11:0] visible_vcount;

  wire TFT_hs;
  wire TFT_vs;

  wire [`Red_Bits - 1 :0]Disp_Red;
  wire [`Green_Bits - 1 :0]Disp_Green;
  wire [`Blue_Bits - 1 :0]Disp_Blue;

  wire Frame_Begin; //一帧图像起始标识信号，ClkDisp时钟域
  wire TFT_de;
  wire Disp_PCLK;
  assign reset=~reset_n;
	initial clk50M = 1;
	
	always#(`CLK_PERIOD/2)clk50M = ~clk50M;
    //assign TFT_rgb={Disp_Red[7:3],Disp_Green[7:2],Disp_Blue[7:3]};

      initial begin
    reset_n = 1'b0;

    #(`CLK_PERIOD*20 + 1 );
    reset_n = 1'b1;
    #(`CLK_PERIOD*50);
    
    @(posedge Frame_Begin);
    @(posedge Frame_Begin);
    @(posedge Frame_Begin);
    $stop;	
  end

  always@(posedge clk50M or negedge reset_n)
  begin
    if(~reset_n)
      TFT_rgb <= 16'd0;
    else if(DataReq == 1'b1)
      TFT_rgb <= TFT_rgb + 1'b1;
    else
      TFT_rgb <= TFT_rgb;
  end  

	disp_driver disp_driver
	(
		.ClkDisp(clk50M),
		.Rst_p(reset),

		.Data(TFT_rgb),
		.DataReq(DataReq),

		.H_Addr(visible_hcount),
		.V_Addr(visible_vcount),
                            
		.Disp_HS(TFT_hs),
		.Disp_VS(TFT_vs),
		.Disp_Red(Disp_Red),
		.Disp_Green(Disp_Green),
		.Disp_Blue(Disp_Blue),
		.Frame_Begin(),
                            
		.Disp_DE(TFT_de),
		.Disp_PCLK(Disp_PCLK)
	);
endmodule
