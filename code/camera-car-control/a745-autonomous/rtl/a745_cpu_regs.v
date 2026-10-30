`timescale 1ns/1ps
`default_nettype none
// PicoRV32 requires two combinational read ports. GW5AT-60B synchronous
// block RAM cannot implement that contract. Separate FF words preserve the
// read semantics instead of allowing the generic array to infer SDPBs.
module a745_cpu_regs(input wire clk,wen,input wire [5:0] waddr,raddr1,raddr2,
 input wire [31:0] wdata,output wire [31:0] rdata1,rdata2);
 wire [1023:0] words;
 assign words[31:0]=32'd0;
 genvar i;
 generate for(i=1;i<32;i=i+1) begin: registers
  reg [31:0] value=0;
  always @(posedge clk) if(wen && waddr==6'(i)) value<=wdata;
  assign words[i*32+:32]=value;
 end endgenerate
 assign rdata1=raddr1[5] ? 32'd0:words[{raddr1[4:0],5'b00000}+:32];
 assign rdata2=raddr2[5] ? 32'd0:words[{raddr2[4:0],5'b00000}+:32];
endmodule
`default_nettype wire
