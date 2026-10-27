module phy_reg_config(
	Clk,
	Rst_n,
	Phy_rst_n,
	Rd_Data,
	Phy_init_done,
	mdc,
	mdio
);
	input Clk;
	input Rst_n;
	output Phy_rst_n;
	output [15:0] Rd_Data;
	output Phy_init_done;
	output mdc;
	inout mdio;

	reg [21:0] reg_data;  //高1位(读/写)+5位寄存器地址+16位寄存器数据
	reg [21:0] mdio_data; //高1位(读/写)+5位寄存器地址+16位寄存器数据
	reg Go;					 //开始传输触发信号
	wire Trans_Done;      //一次传输完成标志

	mdio_bit_shift mdio_bit_shift(
		.Clk        (Clk             ),
		.Rst_n      (Phy_rst_n       ),
		.Mode       (mdio_data[21]   ),
		.Go         (Go              ),
		.Phy_addr   (5'b00101        ),
		.Reg_addr   (mdio_data[20:16]),
		.Tx_Data    (mdio_data[15:0] ),
		.Rx_Data    (Rd_Data         ),
		.Trans_Done (Trans_Done      ),
		.mdc        (mdc             ),
		.mdio       (mdio            )
	);

	/*
	phy要复位，首先将phy_rst_n 拉低至少10ms，之后释放
	phy_rst_n，然后再等至少30ms后，再访问phy register
	*/
	wire start; //为1，开始配置PHY寄存器
	reg [24:0] cnt;
	always @ (posedge Clk or negedge Rst_n)
	begin
		if (!Rst_n)
			cnt <= 'd0;
		else if (cnt < 'd1_500_000)
			cnt <= cnt + 1'b1;
	end

	assign Phy_rst_n = (cnt > 'd500_000);
	assign start = (cnt > 'd1_500_000 - 1'b1);

	//配置PHY寄存器状态控制
	reg [1:0] state;
	reg [2:0] reg_cnt;
	parameter MAX_CNT = 2; //要配置的寄存器个数
	always @ (posedge Clk)
	begin
		if (!start) begin
			state <= 0;
			Go <= 1'b0;
			reg_cnt <= 'd0;
		end else if (reg_cnt < MAX_CNT) begin
			case (state)
				0: begin
						state <= 1;
						Go <= 1'b1;
						mdio_data <= reg_data;
					end
				1: begin
						if (Trans_Done) begin
							state <= 0;
							Go <= 1'b0;
							reg_cnt <= reg_cnt + 1'b1;
						end
					end
			endcase
		end
	end
	
	assign Phy_init_done = (reg_cnt == MAX_CNT);

	//配置寄存器
	always @ (reg_cnt)
	begin
		case (reg_cnt)
		    0 : reg_data <= {1'b0, 5'd0, 16'h1200}; //网卡自动协商
			1 : reg_data <= {1'b1, 5'd0, 16'h0000}; //读取
			default: reg_data <= {1'b0, 5'd0, 16'h1200};
		endcase
	end
	
endmodule
