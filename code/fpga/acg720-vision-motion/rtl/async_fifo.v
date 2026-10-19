`timescale 1ns/1ps
`default_nettype none
// Power-of-two dual-clock FIFO. FWFT: consume current rd_data on rd_en.
// Reset both domains together; deassert each with reset_sync.
module async_fifo #(parameter WIDTH=19,ADDR_BITS=10)(
    input wire wr_clk,wr_rst_n,wr_en,input wire [WIDTH-1:0] wr_data,output reg full,
    input wire rd_clk,rd_rst_n,rd_en,output wire [WIDTH-1:0] rd_data,output reg empty
);
    localparam P=ADDR_BITS+1;
    reg [WIDTH-1:0] mem[0:(1<<ADDR_BITS)-1];
    reg [P-1:0] wb,rb,wg,rg;
    reg [WIDTH-1:0] read_q;
    (* ASYNC_REG="TRUE" *) reg [P-1:0] rg1,rg2,wg1,wg2;
    wire [P-1:0] wn=wb+(wr_en && !full),rn=rb+(rd_en && !empty);
    wire [P-1:0] wgn=(wn>>1)^wn,rgn=(rn>>1)^rn;
    // Synchronous read with next-address prefetch permits block-RAM inference.
    always @(posedge rd_clk) read_q<=mem[rn[ADDR_BITS-1:0]];
    assign rd_data=read_q;
    always @(posedge wr_clk or negedge wr_rst_n)
        if(!wr_rst_n) begin wb<=0;wg<=0;rg1<=0;rg2<=0;full<=0;end
        else begin
            rg1<=rg;rg2<=rg1;wb<=wn;wg<=wgn;
            full<=wgn=={~rg2[P-1:P-2],rg2[P-3:0]};
            if(wr_en && !full) mem[wb[ADDR_BITS-1:0]]<=wr_data;
        end
    always @(posedge rd_clk or negedge rd_rst_n)
        if(!rd_rst_n) begin rb<=0;rg<=0;wg1<=0;wg2<=0;empty<=1;end
        else begin wg1<=wg;wg2<=wg1;rb<=rn;rg<=rgn;empty<=rgn==wg2;end
endmodule
`default_nettype wire
