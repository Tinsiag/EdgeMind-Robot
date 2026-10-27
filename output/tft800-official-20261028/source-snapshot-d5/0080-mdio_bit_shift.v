module mdio_bit_shift(
	Clk,
	Rst_n,

	Mode,
	Go,
	Phy_addr,
	Reg_addr,
	Tx_Data,
	Rx_Data,
	Trans_Done,

	mdc,
	mdio
);
	input Clk;
	input Rst_n;

	input Mode; //1:read,0:write
	input Go;
	input [4:0] Phy_addr;//phy地址
	input [4:0] Reg_addr;//reg地址
	input [15:0] Tx_Data;
	output reg [15:0] Rx_Data;
	output reg Trans_Done;
	output reg mdc;
	inout mdio;

	reg mdio_o;
	reg mdio_oe;

	//系统时钟采用50MHz
	parameter SYS_CLOCK = 50_000_000;
	//MDC总线时钟采用2kHz
	parameter MDC_CLOCK = 2_000;
	//产生时钟mdc计数器最大值
	localparam MDC_CNT_M = SYS_CLOCK/MDC_CLOCK/4 - 1;

	reg [19:0] div_cnt;
	reg en_div_cnt;
	always @ (posedge Clk or negedge Rst_n)
	if (!Rst_n)
		div_cnt <= 'd0;
	else if (en_div_cnt) begin
		if(div_cnt < MDC_CNT_M)
			div_cnt <= div_cnt + 1'b1;
		else
			div_cnt <= 'd0;
	end else
		div_cnt <= 'd0;

	wire mdc_plus = div_cnt == MDC_CNT_M;

	assign mdio = mdio_oe ? mdio_o : 1'bz;

	localparam 
		IDLE  = 8'h01,
		PRE   = 8'h02,
		ST    = 8'h04,
		OP    = 8'h08,
		PHYAD = 8'h10,
		REGAD = 8'h20,
		TA    = 8'h40,
		DATA  = 8'h80;

	//--------------------
	reg [7:0] state;
	reg [7:0] cnt;
	always @ (posedge Clk or negedge Rst_n)
	if (!Rst_n) begin
		Rx_Data <= 'd0;
		mdio_oe <= 1'b0;
		mdio_o <= 1'b1;
		cnt <= 'd0;
		en_div_cnt <= 1'b0;
		Trans_Done <= 1'b0;
		state <= IDLE;
	end else begin
		case (state)
			IDLE:
				begin
					Trans_Done <= 1'b0;
					mdio_oe <= 1'b0;
					if (Go) begin
						en_div_cnt <= 1'b1;
						state <= PRE;
					end else begin
						en_div_cnt <= 1'b0;
						state <= IDLE;
					end
				end
			PRE: //PRE 32'hffff_ffff 32bits
				begin
					if (mdc_plus) begin
						if (cnt == 'd127)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd127)
							state <= ST;
						case (cnt)
							0,4, 8,12,16,20,24,28,32,36,40,44,48,52,56,60,64,
							68,72,76,80,84,88,92,96,100,104,108,112,116,120,124 :
								begin mdio_o <= 1'b1; mdio_oe <= 1'b1; end //set data

							1,5, 9,13,17,21,25,29,33,37,41,45,49,53,57,61,65,
							69,73,77,81,85,89,93,97,101,105,109,113,117,121,125 :
								begin mdc <= 1'b1; end //mdc posedge
							
							2,6,10,14,18,22,26,30,34,38,42,46,50,54,58,62,66,
							70,74,78,82,86,90,94,98,102,106,110,114,118,122,126 :
								begin mdc <= 1'b1; end //mdc keep high
							
							3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63,67,
							71,75,79,83,87,91,95,99,103,107,111,115,119,123,127 :
								begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			ST: //ST 2'b01
				begin
					if (mdc_plus) begin
						if (cnt == 'd7)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd7)
							state <= OP;
						case (cnt)
							0 : begin mdio_o <= 1'b0; mdio_oe <= 1'b1; end //set data
							4 : begin mdio_o <= 1'b1; mdio_oe <= 1'b1; end //set data
							1, 5 : begin mdc <= 1'b1; end //mdc posedge
							2, 6 : begin mdc <= 1'b1; end //mdc keep high
							3, 7 : begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			OP: //OP 01:write, 10:read 2bits
				begin
					if (mdc_plus) begin
						if (cnt == 'd7)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd7)
							state <= PHYAD;
						case (cnt)
							0: begin mdio_o <= Mode; mdio_oe <= 1'b1; end //set data
							4: begin mdio_o <= !Mode; mdio_oe <= 1'b1; end //set data
							1,5: begin mdc <= 1'b1; end //mdc posedge
							2,6: begin mdc <= 1'b1; end //mdc keep high
							3,7: begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			PHYAD: //PHYAD 5bits
				begin
					if (mdc_plus) begin
						if (cnt == 'd19)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd19)
							state <= REGAD;
						case (cnt)
							0,4,8 ,12,16: begin mdio_o <= Phy_addr[4 - cnt[4:2]]; mdio_oe <= 1'b1; end //set data
							1,5,9 ,13,17: begin mdc <= 1'b1; end //mdc posedge
							2,6,10,14,18: begin mdc <= 1'b1; end //mdc keep high
							3,7,11,15,19: begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			REGAD: //REGAD 5bits
				begin
					if (mdc_plus) begin
						if (cnt == 'd19)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd19)
							state <= TA;
						case (cnt)
							0,4,8 ,12,16: begin mdio_o <= Reg_addr[4 - cnt[4:2]]; mdio_oe <= 1'b1; end //set data
							1,5,9 ,13,17: begin mdc <= 1'b1; end //mdc posedge
							2,6,10,14,18: begin mdc <= 1'b1; end //mdc keep high
							3,7,11,15,19: begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			TA: //TA Z0:read, 10:write 2bits
				begin
					if (mdc_plus) begin
						if (cnt == 'd7)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;
						if (cnt == 'd7)
							state <= DATA;
						case (cnt)
							0: begin mdio_o <= 1'b1; mdio_oe <= (Mode == 1'b0); end //set data
							//4: begin mdio_o <= 1'b0; mdio_oe <= 1'b1; end //set data
							4: begin mdio_o <= 1'b0; mdio_oe <= (Mode == 1'b0); end //set data
							1,5: begin mdc <= 1'b1; end //mdc posedge
							2,6: begin mdc <= 1'b1; end //mdc keep high
							3,7: begin mdc <= 1'b0; end //mdc negedge
							default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
						endcase
					end
				end
			DATA:
				begin
					if (mdc_plus) begin
						if (cnt == 'd63)
							cnt <= 'd0;
						else
							cnt <= cnt + 1'b1;

						if (cnt == 'd63) begin
							state <= IDLE;
							Trans_Done <= 1'b1;
						end

						if (Mode) //read data
							case (cnt)
								0,4,8 ,12,16,20,24,28,32,36,40,44,48,52,56,60: begin mdio_oe <= 1'b0; mdc <= 1'b0; end
								1,5,9 ,13,17,21,25,29,33,37,41,45,49,53,57,61: begin mdc <= 1'b1; end //mdc posedge
								2,6,10,14,18,22,26,30,34,38,42,46,50,54,58,62:
									begin
										mdc <= 1'b1;
										Rx_Data <= {Rx_Data[14:0], mdio};
									end //mdc keep high
								3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63: begin mdc <= 1'b0; end //mdc negedge
								default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
							endcase
						else //write data
							case (cnt)
								0,4,8 ,12,16,20,24,28,32,36,40,44,48,52,56,60:
									begin
										mdio_oe <= 1'b1;
										mdio_o <= Tx_Data[15 - cnt[5:2]];
									end //set data
								1,5,9 ,13,17,21,25,29,33,37,41,45,49,53,57,61: begin mdc <= 1'b1; end //mdc posedge
								2,6,10,14,18,22,26,30,34,38,42,46,50,54,58,62: begin mdc <= 1'b1; end //mdc keep high
								3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63: begin mdc <= 1'b0; end //mdc negedge
								default : begin mdio_o <= 1'b1; mdc <= 1'b1; end
							endcase
					end
				end
			default : state <= IDLE;
		endcase
	end

endmodule
