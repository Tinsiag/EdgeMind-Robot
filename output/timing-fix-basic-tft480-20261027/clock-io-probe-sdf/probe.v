module probe(input clk,stop_n,rgmii_rx_clk,input [3:0] rgmii_rxd,input rgmii_rx_ctl,output [15:0] tft_rgb);
wire pll250,tx125,locked;
Gowin_PLL clocks(.clkin(clk),.clkout0(),.clkout1(pll250),.clkout2(),.lock(locked),.mdclk(clk),.reset(!stop_n));
CLKDIV #(.DIV_MODE("2")) tx_divider(.HCLKIN(pll250),.RESETN(locked && stop_n),.CALIB(1'b0),.CLKOUT(tx125));
wire [4:0] delayed;
genvar i;generate for(i=0;i<5;i=i+1)begin:rx
IODELAY #(.C_STATIC_DLY(64),.DYN_DLY_EN("FALSE"),.ADAPT_EN("FALSE")) delay(.DI(i==4?rgmii_rx_ctl:rgmii_rxd[i]),.DO(delayed[i]),.DF(),.DLYSTEP(8'd0),.SDTAP(1'b0),.VALUE(1'b0));
wire a,b;IDDR capture(.D(delayed[i]),.CLK(rgmii_rx_clk),.Q0(a),.Q1(b));
assign tft_rgb[i]=a^b;
end endgenerate
reg [9:0] wa=0,ra=0;(* syn_ramstyle="block_ram" *) reg [8:0] mem[0:1023];reg [8:0] q;
always @(posedge clk)begin wa<=wa+1'b1;mem[wa]<=wa[8:0];end
always @(posedge tx125)begin ra<=ra+1'b1;q<=mem[ra];end
assign tft_rgb[13:5]=q;assign tft_rgb[14]=ra[0];assign tft_rgb[15]=locked;
endmodule
