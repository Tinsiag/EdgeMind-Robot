`timescale 1ns/1ps
`default_nettype none
module uart_rx #(
    parameter integer CLK_HZ = 50000000,
    parameter integer BAUD = 115200
)(
    input wire clk,
    input wire rstn,
    input wire rx,
    output reg [7:0] data,
    output reg valid,
    output reg framing_error
);
    localparam integer CLKS_PER_BIT = CLK_HZ / BAUD;
    localparam integer HALF_BIT = CLKS_PER_BIT / 2;
    localparam integer CW = $clog2(CLKS_PER_BIT + 1);
    reg [2:0] sync;
    reg busy;
    reg [CW-1:0] count;
    reg [3:0] bit_index;
    reg [7:0] shift;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin
            sync <= 3'b111; busy <= 0; count <= 0; bit_index <= 0;
            shift <= 0; data <= 0; valid <= 0; framing_error <= 0;
        end else begin
            sync <= {sync[1:0], rx};
            valid <= 0; framing_error <= 0;
            if (!busy) begin
                if (!sync[2]) begin
                    busy <= 1; count <= HALF_BIT; bit_index <= 0;
                end
            end else if (count != 0) begin
                count <= count - 1'b1;
            end else begin
                count <= CLKS_PER_BIT - 1;
                if (bit_index == 0) begin
                    if (sync[2]) begin busy <= 0; framing_error <= 1; end
                    else bit_index <= bit_index + 1'b1;
                end else if (bit_index <= 8) begin
                    shift[bit_index-1] <= sync[2];
                    bit_index <= bit_index + 1'b1;
                end else begin
                    busy <= 0;
                    if (!sync[2]) begin framing_error <= 1; end
                    else begin data <= shift; valid <= 1; end
                end
            end
        end
    end
endmodule
`default_nettype wire
