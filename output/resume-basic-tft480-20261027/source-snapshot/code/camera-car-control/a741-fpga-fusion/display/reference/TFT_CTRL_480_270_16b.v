/*============================================================================
*
*  LOGIC CORE:          TFT驱动模块		
*  MODULE NAME:         TFT_CTRL()
*  COMPANY:             芯航线电子工作室
*                       http://xiaomeige.taobao.com
*	author:					小梅哥
*	author QQ Group：472607506
*  REVISION HISTORY:  
*
*    Revision 1.0  01/01/2016     Description: Initial Release.
*
*  FUNCTIONAL DESCRIPTION:
===========================================================================*/
module TFT_CTRL_480_270_16b(
	Clk9M,	//系统输入时钟9MHZ
	Rst_n,	//复位输入，低电平复位
	data_in,	//待显示数据
	hcount,		//TFT行扫描计数器
	vcount,		//TFT场扫描计数器
	TFT_RGB,	//TFT数据输出
	TFT_HS,		//TFT行同步信号
	TFT_VS,		//TFT场同步信号
	TFT_CLK,		//TFT像素时钟
	TFT_DE,		//TFT数据使能
	TFT_PWM		//TFT背光控制
);
			
	//----------------模块输入端口----------------
	input  Clk9M;          //系统输入时钟9MHZ
	input  Rst_n;
	input  [15:0]data_in;     //待显示数据

	//----------------模块输出端口----------------
	output [9:0]hcount;
	output [9:0]vcount;
	output [15:0]TFT_RGB;  //TFT数据输出
	output TFT_HS;           //TFT行同步信号
	output TFT_VS;           //TFT场同步信号
	output TFT_CLK;
	output TFT_DE;
	output TFT_PWM;

	//----------------内部寄存器定义----------------
	reg [9:0] hcount_r;     //TFT行扫描计数器
	reg [9:0] vcount_r;     //TFT场扫描计数器
	//----------------内部连线定义----------------
	wire hcount_ov;
	wire vcount_ov;
	wire dat_act;//有效显示区标定

	//TFT行、场扫描时序参数表
	parameter TFT_HS_end=10'd40,
				 hdat_begin=10'd42,
				 hdat_end=10'd522,
				 hpixel_end=10'd524,
				 TFT_VS_end=10'd9,
				 vdat_begin=10'd11,
				 vdat_end=10'd283,
				 vline_end=10'd285;

	assign hcount=hcount_r-hdat_begin;
	assign vcount=vcount_r-vdat_begin;
	
	assign TFT_CLK = Clk9M;
	assign TFT_DE = dat_act;
	assign TFT_PWM = Rst_n;

	//**********************TFT驱动部分**********************
	//行扫描
	always@(posedge Clk9M or negedge Rst_n)
	if(!Rst_n)
		hcount_r<=10'd0;
	else if(hcount_ov)
		hcount_r<=10'd0;
	else
		hcount_r<=hcount_r+10'd1;

	assign hcount_ov=(hcount_r==hpixel_end);

	//场扫描
	always@(posedge Clk9M or negedge Rst_n)
	if(!Rst_n)
		vcount_r<=10'd0;
	else if(hcount_ov) begin
		if(vcount_ov)
			vcount_r<=10'd0;
		else
			vcount_r<=vcount_r+10'd1;
	end
	else 
		vcount_r<=vcount_r;
		
	assign 	vcount_ov=(vcount_r==vline_end);

	//数据、同步信号输出
	assign dat_act=((hcount_r>=hdat_begin)&&(hcount_r<hdat_end))
					&&((vcount_r>=vdat_begin)&&(vcount_r<vdat_end));
					
	assign TFT_HS=(hcount_r>TFT_HS_end);
	assign TFT_VS=(vcount_r>TFT_VS_end);
	assign TFT_RGB=(dat_act)?data_in:16'h0000;
		
endmodule 
