`timescale 1ns/1ps
`default_nettype none
// Power-of-two dual-clock FIFO. FWFT: consume current rd_data on rd_en.
// Reset both domains together; deassert each with reset_sync.
// LEVELS=1 adds occupancy counters. They cost registers and routing in both
// clock domains, so they stay off by default: only the EV10 video FIFO needs
// them, and enabling them everywhere pushed the DDR ui_clk domain into hold
// violations. With LEVELS=0 the instance is identical to the original FIFO.
module async_fifo #(parameter WIDTH=19,ADDR_BITS=10,LEVELS=0)(
    input wire wr_clk,wr_rst_n,wr_en,input wire [WIDTH-1:0] wr_data,output reg full,
    // Conservative write-side occupancy (lags reads by the 2-flop sync).
    output wire [ADDR_BITS:0] wr_level,
    input wire rd_clk,rd_rst_n,rd_en,output wire [WIDTH-1:0] rd_data,output reg empty,
    // Conservative read-side occupancy (lags writes by the 2-flop sync).
    output wire [ADDR_BITS:0] rd_level
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
    // Gray-to-binary of the synchronised opposite pointer. The XOR chain is
    // registered before the subtraction so neither level computation adds a
    // long combinational path; each level then lags by one extra cycle in the
    // conservative direction (rd_level under-reports data available to the
    // reader, wr_level over-reports space in use for the writer).
    generate
    if(LEVELS) begin : g_levels
        reg [P-1:0] wb_rd;
        integer gi;
        always @* begin
            wb_rd[P-1]=wg2[P-1];
            for(gi=P-2;gi>=0;gi=gi-1) wb_rd[gi]=wb_rd[gi+1]^wg2[gi];
        end
        reg [P-1:0] rb_wr;
        integer gj;
        always @* begin
            rb_wr[P-1]=rg2[P-1];
            for(gj=P-2;gj>=0;gj=gj-1) rb_wr[gj]=rb_wr[gj+1]^rg2[gj];
        end
        wire [P-1:0] wn=write_accept ? wb_inc:wb;
        reg [P-1:0] wb_rd_q,rb_wr_q;
        reg [P-1:0] wr_level_r,rd_level_r;
        always @(posedge wr_clk or negedge wr_rst_n)
            if(!wr_rst_n) begin rb_wr_q<=0;wr_level_r<=0;end
            else begin rb_wr_q<=rb_wr;wr_level_r<=wn-rb_wr_q;end
        always @(posedge rd_clk or negedge rd_rst_n)
            if(!rd_rst_n) begin wb_rd_q<=0;rd_level_r<=0;end
            else begin wb_rd_q<=wb_rd;rd_level_r<=wb_rd_q-rn;end
        assign wr_level=wr_level_r;
        assign rd_level=rd_level_r;
    end else begin : g_no_levels
        assign wr_level={P{1'b0}};
        assign rd_level={P{1'b0}};
    end
    endgenerate
endmodule
`default_nettype wire
