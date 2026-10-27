`timescale 1ns/1ps
module official_probe(input wire clk50M,reset_n,output wire [15:0] TFT_rgb,
 output wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm,output wire [7:0] led,
 output wire left_in1,left_in2,right_in1,right_in2);
 wire [15:0] rgb;wire hs,vs,de,pwm,pclk;
 tft_ctrl_test official(.clk50M(clk50M),.reset_n(reset_n),.TFT_rgb(rgb),
  .TFT_hs(hs),.TFT_vs(vs),.TFT_clk(pclk),.TFT_de(de),.TFT_pwm(pwm));
 // Preserve all official RTL. Retiming outputs on the falling edge centers
 // stable data on the documented WKS43189 rising-edge sample; no ODDR path.
 (* syn_preserve=1, syn_keep=1 *) reg [18:0] pins=0;
 always @(negedge pclk) pins<={de,hs,vs,rgb};
 assign {TFT_de,TFT_hs,TFT_vs,TFT_rgb}=pins;
 assign TFT_clk=pclk;assign TFT_pwm=pwm;
 reg [25:0] sys_count=0;reg [4:0] frames=0;reg old_vs=0;
 always @(posedge clk50M or negedge reset_n) if(!reset_n) sys_count<=0;else sys_count<=sys_count+1'b1;
 always @(posedge pclk or negedge reset_n) if(!reset_n) begin frames<=0;old_vs<=0;end
 else begin old_vs<=vs;if(vs && !old_vs) frames<=frames+1'b1;end
 assign led={5'b00000,frames[4],sys_count[24],1'b1};
 assign left_in1=1'b0;assign left_in2=1'b0;assign right_in1=1'b0;assign right_in2=1'b0;
endmodule
