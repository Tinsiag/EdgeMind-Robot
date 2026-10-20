`timescale 1ns/1ps
`default_nettype none
module uart_tx #(
    parameter integer CLK_HZ = 50000000,
    parameter integer BAUD = 115200
)(
    input wire clk,
    input wire rstn,
    input wire start,
    input wire [7:0] data,
    output reg tx,
    output reg busy
);
    localparam integer CLKS_PER_BIT = CLK_HZ / BAUD;
    localparam integer CW = $clog2(CLKS_PER_BIT + 1);
    reg [CW-1:0] count;
    reg [3:0] bit_index;
    reg [9:0] frame;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin tx <= 1; busy <= 0; count <= 0; bit_index <= 0; frame <= 10'h3ff; end
        else if (!busy) begin
            tx <= 1;
            if (start) begin
                frame <= {1'b1, data, 1'b0};
                tx <= 0; busy <= 1; count <= CLKS_PER_BIT - 1; bit_index <= 0;
            end
        end else if (count != 0) count <= count - 1'b1;
        else begin
            count <= CLKS_PER_BIT - 1;
            if (bit_index == 9) begin busy <= 0; tx <= 1; end
            else begin bit_index <= bit_index + 1'b1; tx <= frame[bit_index + 1'b1]; end
        end
    end
endmodule
`default_nettype wire
