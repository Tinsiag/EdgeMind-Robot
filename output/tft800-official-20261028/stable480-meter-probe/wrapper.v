`timescale 1ns/1ps
module official_probe #(parameter WINDOW_CYCLES=50000000)(
 input wire clk50M,reset_n,
 inout wire [15:0] TFT_rgb,
 inout wire TFT_hs,TFT_vs,TFT_clk,TFT_de,TFT_pwm,
 output wire [7:0] led,
 output wire left_in1,left_in2,right_in1,right_in2);
 wire [15:0] rgb;
 wire hs,vs,de,pwm,pclk;
 tft_ctrl_test official(.clk50M(clk50M),.reset_n(reset_n),.TFT_rgb(rgb),
  .TFT_hs(hs),.TFT_vs(vs),.TFT_clk(pclk),.TFT_de(de),.TFT_pwm(pwm));
 // AT043TN24 hypothesis: data is stable around external PCLK falling edge.
 // Retain the preceding candidate's scan, color generator and PCLK polarity.
 (* syn_preserve=1, syn_keep=1 *) reg [18:0] pins=0;
 always @(negedge pclk) pins<={de,hs,vs,rgb};
 wire read_clk,read_de,read_bl,read_hs,read_vs;
 wire [15:0] read_rgb;
 IOBUF clock_pad(.IO(TFT_clk),.I(~pclk),.OEN(1'b0),.O(read_clk));
 IOBUF de_pad(.IO(TFT_de),.I(pins[18]),.OEN(1'b0),.O(read_de));
 IOBUF bl_pad(.IO(TFT_pwm),.I(1'b1),.OEN(1'b0),.O(read_bl));
 IOBUF hs_pad(.IO(TFT_hs),.I(pins[17]),.OEN(1'b0),.O(read_hs));
 IOBUF vs_pad(.IO(TFT_vs),.I(pins[16]),.OEN(1'b0),.O(read_vs));
 genvar b;
 generate for(b=0;b<16;b=b+1) begin:rgb_pads
  IOBUF pad(.IO(TFT_rgb[b]),.I(pins[b]),.OEN(1'b0),.O(read_rgb[b]));
 end endgenerate

 // Independently sample actual pad inputs in the 50MHz reference domain.
 wire [19:0] read_all={read_bl,read_de,read_hs,read_vs,read_rgb};
 wire [19:0] expected_all={1'b1,pins};
 (* ASYNC_REG="TRUE" *) reg [19:0] read_s1=0,read_s2=0;
 (* ASYNC_REG="TRUE" *) reg [19:0] expect_s1=0,expect_s2=0;
 (* ASYNC_REG="TRUE" *) reg [1:0] clock_sync=0,lock_sync=0;
 reg old_clock=0,old_hs=0,old_vs=0,old_de=0;
 reg [19:0] old_expected=0;
 reg [2:0] stable_cycles=0;
 wire rise_clk=clock_sync[1] && !old_clock;
 wire rise_hs=read_s2[17] && !old_hs;
 wire rise_vs=read_s2[16] && !old_vs;
 wire rise_de=read_s2[18] && !old_de;
 wire mismatch_now=(stable_cycles>=3) && (read_s2!=expect_s2);
 reg mismatch_seen=0;
 reg [25:0] window_count=0,clock_edges=0,de_samples=0;
 reg [15:0] hs_edges=0,de_edges=0;
 reg [7:0] vs_edges=0;
 reg clock_ok=0,raster_ok=0,pads_ok=0;
 localparam EXPECT_CLOCK=(WINDOW_CYCLES*9)/50;
 localparam EXPECT_HS=EXPECT_CLOCK/525;
 localparam EXPECT_VS=EXPECT_CLOCK/(525*286);
 localparam [63:0] DE_PRODUCT=64'd130560*WINDOW_CYCLES;
 localparam EXPECT_DE_SAMPLES=DE_PRODUCT/150150;
 localparam [63:0] EDGE_PRODUCT=64'd272*EXPECT_CLOCK;
 localparam EXPECT_DE_EDGES=EDGE_PRODUCT/150150;
 // Line/frame rounding and partial active-frame windows are bounded.
 localparam DE_SAMPLE_TOLERANCE=100000;
 localparam DE_EDGE_TOLERANCE=32;
 reg [25:0] heartbeat=0;
 reg [4:0] frames=0;
 always @(posedge clk50M or negedge reset_n)
  if(!reset_n) begin
   read_s1<=0;read_s2<=0;expect_s1<=0;expect_s2<=0;clock_sync<=0;lock_sync<=0;
   old_clock<=0;old_hs<=0;old_vs<=0;old_de<=0;old_expected<=0;stable_cycles<=0;
   mismatch_seen<=0;window_count<=0;clock_edges<=0;hs_edges<=0;vs_edges<=0;
   de_edges<=0;de_samples<=0;clock_ok<=0;raster_ok<=0;pads_ok<=0;heartbeat<=0;frames<=0;
  end else begin
   read_s1<=read_all;read_s2<=read_s1;expect_s1<=expected_all;expect_s2<=expect_s1;
   clock_sync<={clock_sync[0],read_clk};lock_sync<={lock_sync[0],official.pll_locked};
   old_clock<=clock_sync[1];old_hs<=read_s2[17];old_vs<=read_s2[16];old_de<=read_s2[18];
   old_expected<=expect_s2;
   if(expect_s2!=old_expected)stable_cycles<=0;
   else if(stable_cycles!=7)stable_cycles<=stable_cycles+1'b1;
   heartbeat<=heartbeat+1'b1;
   if(rise_vs)frames<=frames+1'b1;
   if(!lock_sync[1]) begin
    window_count<=0;clock_edges<=0;hs_edges<=0;vs_edges<=0;de_edges<=0;de_samples<=0;
    mismatch_seen<=0;clock_ok<=0;raster_ok<=0;pads_ok<=0;
   end else if(window_count==WINDOW_CYCLES-1) begin
    clock_ok<=(clock_edges+rise_clk>=EXPECT_CLOCK-4) && (clock_edges+rise_clk<=EXPECT_CLOCK+4);
    raster_ok<=(hs_edges+rise_hs>=EXPECT_HS-2) && (hs_edges+rise_hs<=EXPECT_HS+2)
     && (vs_edges+rise_vs+2>=EXPECT_VS) && (vs_edges+rise_vs<=EXPECT_VS+2)
     && (de_edges+rise_de+DE_EDGE_TOLERANCE>=EXPECT_DE_EDGES)
     && (de_edges+rise_de<=EXPECT_DE_EDGES+DE_EDGE_TOLERANCE)
     && (de_samples+read_s2[18]+DE_SAMPLE_TOLERANCE>=EXPECT_DE_SAMPLES)
     && (de_samples+read_s2[18]<=EXPECT_DE_SAMPLES+DE_SAMPLE_TOLERANCE);
    pads_ok<=!mismatch_seen && !mismatch_now;
    window_count<=0;clock_edges<=0;hs_edges<=0;vs_edges<=0;de_edges<=0;de_samples<=0;mismatch_seen<=0;
   end else begin
    window_count<=window_count+1'b1;clock_edges<=clock_edges+rise_clk;
    hs_edges<=hs_edges+rise_hs;vs_edges<=vs_edges+rise_vs;de_edges<=de_edges+rise_de;
    de_samples<=de_samples+read_s2[18];if(mismatch_now)mismatch_seen<=1;
   end
  end
 assign led={lock_sync[1] && clock_ok && raster_ok && pads_ok,pads_ok,raster_ok,clock_ok,
             read_s2[19],frames[4],heartbeat[24],lock_sync[1]};
 assign left_in1=1'b0,left_in2=1'b0,right_in1=1'b0,right_in2=1'b0;
endmodule
