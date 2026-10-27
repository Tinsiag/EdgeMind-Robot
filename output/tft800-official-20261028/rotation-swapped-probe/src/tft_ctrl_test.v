//////////////////////////////////////////////////////////////////////////////////
// Company: 武汉芯路恒科技有限公司
// Engineer: www.corecourse.cn
// 
// Create Date: 2020/07/20 00:00:00
// Design Name: tft_ctrl_test
// Module Name: tft_ctrl_test
// Project Name: tft_ctrl_test
// Description: 5寸TFT显示屏控制器板级测试
// 
// Dependencies: tft顶层文件，协调锁相环和驱动程序的工作
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////

module tft_ctrl_test(
	clk50M,
	reset_n,

	TFT_rgb,
	TFT_hs,
	TFT_vs,
	TFT_clk,
	TFT_de,
	TFT_pwm
);
	wire reset=~reset_n;
	input clk50M;   //系统时钟输入，50M
	input reset_n;  //复位信号输入，低有效
  
	output [15:0]TFT_rgb;  //TFT数据输出
	output TFT_hs;   //TFT行同步信号
	output TFT_vs;   //TFT场同步信号
	output TFT_clk;  //TFT像素时钟
	output TFT_de;   //TFT数据使能
	output TFT_pwm;  //TFT背光控制

  //定义颜色编码
	localparam 
    BLACK = 16'h0000, //黑色
    BLUE = 16'h001F, //蓝色
    RED = 16'hF800, //红色
    PURPPLE	= 16'hF81F, //紫色
    GREEN = 16'h07E0, //绿色
    CYAN = 16'h07FF, //青色
    YELLOW	= 16'hFFE0, //黄色
    WHITE = 16'hFFFF; //白色
    
  //定义每个像素块的默认显示颜色值
	localparam 
    R0_C0 = BLACK,	 //第0行0列像素块
    R0_C1 = BLUE,	   //第0行1列像素块
    R1_C0 = RED,	   //第1行0列像素块
    R1_C1 = PURPPLE, //第1行1列像素块
    R2_C0 = GREEN,	 //第2行0列像素块
    R2_C1 = CYAN,	   //第2行1列像素块
    R3_C0 = YELLOW,	 //第3行0列像素块
    R3_C1 = WHITE;	 //第3行1列像素块
	
	wire pll_locked;
	wire tft_reset_p;
	wire clk_ctrl;
	reg [15:0]disp_data;
	wire disp_data_req;
	wire [11:0]visible_hcount;
	wire [11:0]visible_vcount;
	wire R0_act;
	wire R1_act;
	wire R2_act;
	wire R3_act; 
	wire C0_act;
	wire C1_act;
	wire R0_C0_act;
	wire R0_C1_act;
	wire R1_C0_act;
	wire R1_C1_act;
	wire R2_C0_act;
	wire R2_C1_act;
	wire R3_C0_act;
	wire R3_C1_act;
	wire [4:0]Disp_Red;
	wire [5:0]Disp_Green;
	wire [4:0]Disp_Blue;
	wire TFT_pwm;
	wire Disp_PCLK;

	assign R0_act = visible_vcount >= 0   && visible_vcount < 120; //正在扫描第0行条纹
	assign R1_act = visible_vcount >= 120 && visible_vcount < 240; //正在扫描第1行条纹
	assign R2_act = visible_vcount >= 240 && visible_vcount < 360; //正在扫描第2行条纹
	assign R3_act = visible_vcount >= 360 && visible_vcount < 480; //正在扫描第3行条纹
	assign C0_act = visible_hcount >= 0   && visible_hcount < 400; //正在扫描第0列条纹
	assign C1_act = visible_hcount >= 400 && visible_hcount < 800; //正在扫描第1列条纹

	assign R0_C0_act = disp_data_req && R0_act && C0_act;	//第0行0列像素块处于被扫描中标志信号
	assign R0_C1_act = disp_data_req && R0_act && C1_act;	//第0行1列像素块处于被扫描中标志信号
	assign R1_C0_act = disp_data_req && R1_act && C0_act;	//第1行0列像素块处于被扫描中标志信号
	assign R1_C1_act = disp_data_req && R1_act && C1_act;	//第1行1列像素块处于被扫描中标志信号
	assign R2_C0_act = disp_data_req && R2_act && C0_act;	//第2行0列像素块处于被扫描中标志信号
	assign R2_C1_act = disp_data_req && R2_act && C1_act;	//第2行1列像素块处于被扫描中标志信号
	assign R3_C0_act = disp_data_req && R3_act && C0_act;	//第3行0列像素块处于被扫描中标志信号
	assign R3_C1_act = disp_data_req && R3_act && C1_act;	//第3行1列像素块处于被扫描中标志信号
	
//	assign tft_reset_n = pll_locked;
	reg [1:0] tft_ready;
    always @(posedge clk_ctrl or negedge pll_locked)
      if(!pll_locked) tft_ready<=0;else tft_ready<={tft_ready[0],1'b1};
    assign tft_reset_p = ~tft_ready[1]; //锁相环提供的TFT屏复位信号进行取反，满足高电平复位


    Gowin_PLL Gowin_PLL(
        .clkin(clk50M), //input  clkin
        .clkout0(clk_ctrl), //output  clkout0
        .lock(pll_locked), //output  lock
        .mdclk(clk50M), //input  mdclk
        .reset(~reset_n) //input  reset
);

	disp_driver disp_driver
	(
		.ClkDisp(clk_ctrl),
		.Rst_p(tft_reset_p),

		.Data(disp_data),
		.DataReq(disp_data_req),

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
	
	assign TFT_rgb={Disp_Red,Disp_Green,Disp_Blue};
	assign TFT_clk=Disp_PCLK;
	assign TFT_pwm=1'b1;
	
	always@(*)
		case({R3_C1_act,R3_C0_act,R2_C1_act,R2_C0_act,
				  R1_C1_act,R1_C0_act,R0_C1_act,R0_C0_act})
			8'b0000_0001:disp_data = R0_C0;
			8'b0000_0010:disp_data = R0_C1;
			8'b0000_0100:disp_data = R1_C0;
			8'b0000_1000:disp_data = R1_C1;
			8'b0001_0000:disp_data = R2_C0;
			8'b0010_0000:disp_data = R2_C1;
			8'b0100_0000:disp_data = R3_C0;
			8'b1000_0000:disp_data = R3_C1;
			default:disp_data = R0_C0;
		endcase
		
endmodule
