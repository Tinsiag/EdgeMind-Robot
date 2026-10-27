`timescale 1ns/1ps
`default_nettype none
module quadrature_decoder(
    input wire clk,
    input wire rstn,
    input wire a,
    input wire b,
    input wire invert,
    output reg signed [1:0] step,
    output reg invalid
);
    reg [2:0] a_sync, b_sync;
    reg [1:0] previous;
    // Fill the three-stage synchronizer before adopting the initial AB state.
    reg [2:0] sync_ready;
    reg initialized;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin a_sync <= 0; b_sync <= 0; previous <= 0; step <= 0; invalid <= 0; sync_ready <= 0; initialized <= 0; end
        else begin
            a_sync <= {a_sync[1:0], a}; b_sync <= {b_sync[1:0], b};
            step <= 0; invalid <= 0;
            sync_ready <= {sync_ready[1:0], 1'b1};
            if (!initialized) begin
                if (&sync_ready) begin
                    previous <= {a_sync[2], b_sync[2]};
                    initialized <= 1;
                end
            end else begin
            case ({previous, {a_sync[2], b_sync[2]}})
                4'b0001,4'b0111,4'b1110,4'b1000: step <= invert ? -2'sd1 : 2'sd1;
                4'b0010,4'b1011,4'b1101,4'b0100: step <= invert ? 2'sd1 : -2'sd1;
                4'b0000,4'b0101,4'b1010,4'b1111: step <= 0;
                default: invalid <= 1;
            endcase
            previous <= {a_sync[2], b_sync[2]};
            end
        end
    end
endmodule
`default_nettype wire
