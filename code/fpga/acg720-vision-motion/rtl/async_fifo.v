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
    wire write_accept=wr_en && !full,read_accept=rd_en && !empty;
    // Compute increment and Gray comparisons before selecting by enable.
    // This keeps the enable/reset path out of the binary carry chain and
    // preserves the same FWFT pointer and flag updates on each clock edge.
    wire [P-1:0] wb_inc=wb+1'b1,rb_inc=rb+1'b1;
    wire [P-1:0] wg_inc=(wb_inc>>1)^wb_inc,rg_inc=(rb_inc>>1)^rb_inc;
    wire [P-1:0] rn=read_accept ? rb_inc:rb;
    wire [P-1:0] full_pointer={~rg2[P-1:P-2],rg2[P-3:0]};
    // Synchronous read with next-address prefetch permits block-RAM inference.
    always @(posedge rd_clk) read_q<=mem[rn[ADDR_BITS-1:0]];
    assign rd_data=read_q;
    always @(posedge wr_clk or negedge wr_rst_n)
        if(!wr_rst_n) begin wb<=0;wg<=0;rg1<=0;rg2<=0;full<=0;end
        else begin
            rg1<=rg;rg2<=rg1;
            if(write_accept) begin wb<=wb_inc;wg<=wg_inc;end
            full<=write_accept ? wg_inc==full_pointer:wg==full_pointer;
            if(write_accept) mem[wb[ADDR_BITS-1:0]]<=wr_data;
        end
    always @(posedge rd_clk or negedge rd_rst_n)
        if(!rd_rst_n) begin rb<=0;rg<=0;wg1<=0;wg2<=0;empty<=1;end
        else begin
            wg1<=wg;wg2<=wg1;
            if(read_accept) begin rb<=rb_inc;rg<=rg_inc;end
            empty<=read_accept ? rg_inc==wg2:rg==wg2;
        end
endmodule
`default_nettype wire
