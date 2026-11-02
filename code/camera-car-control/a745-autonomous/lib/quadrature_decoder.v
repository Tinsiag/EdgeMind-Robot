`timescale 1ns/1ps
`default_nettype none
// Qualify the complete synchronized AB pair. Independent per-pin filters
// could invent a different sequence when both pins contain a short spike.
module quadrature_decoder #(parameter integer FILTER_CYCLES=100)(
    input wire clk,
    input wire rstn,
    input wire a,
    input wire b,
    input wire invert,
    output reg signed [1:0] step,
    output reg invalid
);
    reg [2:0] a_sync, b_sync;
    localparam integer QUALIFY_CYCLES=FILTER_CYCLES<2 ? 2:FILTER_CYCLES;
    localparam integer FILTER_BITS=$clog2(QUALIFY_CYCLES+1);
    reg [1:0] previous,candidate;
    reg [FILTER_BITS-1:0] stable_count;
    // Fill the three-stage synchronizer before adopting the initial AB state.
    reg [2:0] sync_ready;
    reg initialized;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin a_sync <= 0; b_sync <= 0; previous <= 0; candidate<=0;stable_count<=0;step <= 0; invalid <= 0; sync_ready <= 0; initialized <= 0; end
        else begin
            a_sync <= {a_sync[1:0], a}; b_sync <= {b_sync[1:0], b};
            step <= 0; invalid <= 0;
            sync_ready <= {sync_ready[1:0], 1'b1};
            if (!(&sync_ready)) begin
                candidate<={a_sync[2],b_sync[2]};stable_count<=0;
            end else if ({a_sync[2],b_sync[2]}!=candidate) begin
                candidate<={a_sync[2],b_sync[2]};stable_count<=1;
            end else if(stable_count<QUALIFY_CYCLES-1) begin
                stable_count<=stable_count+1'b1;
            end else if(!initialized) begin
                previous<=candidate;initialized<=1;
            end else if(candidate!=previous) begin
            case ({previous,candidate})
                4'b0001,4'b0111,4'b1110,4'b1000: step <= invert ? -2'sd1 : 2'sd1;
                4'b0010,4'b1011,4'b1101,4'b0100: step <= invert ? 2'sd1 : -2'sd1;
                4'b0000,4'b0101,4'b1010,4'b1111: step <= 0;
                default: invalid <= 1;
            endcase
            previous <= candidate;
            end
        end
    end
endmodule
`default_nettype wire
