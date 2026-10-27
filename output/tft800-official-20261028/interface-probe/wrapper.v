`timescale 1ns/1ps
module official_probe(input wire clk50M,reset_n,output wire [15:0] TFT_rgb,
 output wire TFT_hs,TFT_vs,inout wire TFT_clk,TFT_de,TFT_pwm,output wire [7:0] led,
 output wire left_in1,left_in2,right_in1,right_in2);
 wire [15:0] rgb;wire hs,vs,de,pwm,pclk;
 tft_ctrl_test official(.clk50M(clk50M),.reset_n(reset_n),.TFT_rgb(rgb),
  .TFT_hs(hs),.TFT_vs(vs),.TFT_clk(pclk),.TFT_de(de),.TFT_pwm(pwm));
 // Preserve all official RTL. Retiming outputs on the falling edge centers
 // stable data on the documented WKS43189 rising-edge sample; no ODDR path.
 (* syn_preserve=1, syn_keep=1 *) reg [18:0] pins=0;
 always @(negedge pclk) pins<={de,hs,vs,rgb};
 assign {TFT_hs,TFT_vs,TFT_rgb}=pins[17:0];
 wire read_clk,read_de,read_bl;
 IOBUF clock_pad(.IO(TFT_clk),.I(pclk),.OEN(1'b0),.O(read_clk));
 IOBUF de_pad(.IO(TFT_de),.I(pins[18]),.OEN(1'b0),.O(read_de));
 IOBUF bl_pad(.IO(TFT_pwm),.I(sys_count[25]),.OEN(1'b0),.O(read_bl));
 (* ASYNC_REG="TRUE" *) reg [1:0] read_clk_sync,read_de_sync,read_bl_sync;
 reg read_clk_old=0,seen_de=0;reg [23:0] edge_count=0;
 always @(posedge clk50M or negedge reset_n)
  if(!reset_n) begin read_clk_sync<=0;read_de_sync<=0;read_bl_sync<=0;read_clk_old<=0;edge_count<=0;seen_de<=0;end
  else begin
   read_clk_sync<={read_clk_sync[0],read_clk};read_de_sync<={read_de_sync[0],read_de};read_bl_sync<={read_bl_sync[0],read_bl};
   read_clk_old<=read_clk_sync[1];if(read_clk_sync[1] && !read_clk_old) edge_count<=edge_count+1'b1;
   if(read_de_sync[1]) seen_de<=1;
  end
 reg [25:0] sys_count=0;reg [4:0] frames=0;reg old_vs=0;
 always @(posedge clk50M or negedge reset_n) if(!reset_n) sys_count<=0;else sys_count<=sys_count+1'b1;
 always @(posedge pclk or negedge reset_n) if(!reset_n) begin frames<=0;old_vs<=0;end
 else begin old_vs<=vs;if(vs && !old_vs) frames<=frames+1'b1;end
 assign led={2'b00,seen_de,edge_count[22],read_bl_sync[1],frames[4],sys_count[24],1'b1};
 assign left_in1=1'b0;assign left_in2=1'b0;assign right_in1=1'b0;assign right_in2=1'b0;
endmodule
