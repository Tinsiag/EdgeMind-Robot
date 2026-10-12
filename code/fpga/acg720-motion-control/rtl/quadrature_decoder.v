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
    reg [1:0] current;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin a_sync <= 0; b_sync <= 0; previous <= 0; step <= 0; invalid <= 0; end
        else begin
            a_sync <= {a_sync[1:0], a}; b_sync <= {b_sync[1:0], b};
            step <= 0; invalid <= 0;
            current <= {a_sync[2], b_sync[2]};
            case ({previous, {a_sync[2], b_sync[2]}})
                4'b0001,4'b0111,4'b1110,4'b1000: step <= invert ? -2'sd1 : 2'sd1;
                4'b0010,4'b1011,4'b1101,4'b0100: step <= invert ? 2'sd1 : -2'sd1;
                4'b0000,4'b0101,4'b1010,4'b1111: step <= 0;
                default: invalid <= 1;
            endcase
            previous <= {a_sync[2], b_sync[2]};
        end
    end
endmodule
`default_nettype wire
