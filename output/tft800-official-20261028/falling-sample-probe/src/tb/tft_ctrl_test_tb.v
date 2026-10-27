/////////////////////////////////////////////////////////////////////////////////
// Company: 武汉芯路恒科技有限公司
// Engineer: 小梅哥团队
// Web: www.corecourse.cn
// 
// Create Date: 2020/07/20 00:00:00
// Design Name: tft_ctrl_test
// Module Name: tft_ctrl_test_tb
// Project Name: tft_ctrl_test
// Target Devices: XC7A35T-2FGG484I
// Tool Versions: Vivado 2018.3
// Description: tft_ctrl_test模块仿真文件
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
`timescale 1ns / 1ns
`define CLK_PERIOD 20

module tft_ctrl_test_tb();

	reg          clk50M         ;
	reg          reset_n        ;

	wire  [15:0] TFT_rgb        ;
	wire         TFT_hs         ;
	wire         TFT_vs         ;
	wire         TFT_clk        ;
	wire         TFT_de         ;
	wire         TFT_pwm        ;

	initial clk50M = 1;
	always#(`CLK_PERIOD/2)clk50M = ~clk50M;

  initial begin
    reset_n = 1'b0;
    #(`CLK_PERIOD*20 + 1 );
    reset_n = 1'b1;
    #(`CLK_PERIOD*50);
    
    @(posedge TFT_vs);
    @(posedge TFT_vs);
    $stop;	
  end

tft_ctrl_test tft_ctrl_test
(
	.clk50M         (clk50M        ), //50MHz时钟输入
	.reset_n        (reset_n       ), //异步复位信号，低有效

	.TFT_rgb        (TFT_rgb       ), //TFT数据输出
	.TFT_hs         (TFT_hs        ), //TFT行同步信号
	.TFT_vs         (TFT_vs        ), //TFT场同步信号
	.TFT_clk        (TFT_clk       ), //TFT像素时钟
	.TFT_de         (TFT_de        ), //TFT数据使能
	.TFT_pwm        (TFT_pwm       )  //TFT背光控制
);

endmodule
