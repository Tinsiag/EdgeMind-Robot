`timescale 1ns/1ps
`default_nettype none
// One registered AXI stream beat separates byte selection from UDP checksum math.
module a741_tx_stage(
    input wire clk,rst_n,input wire [7:0] source_data,input wire source_valid,source_last,
    output wire source_ready,output reg [7:0] data,output reg valid,last,input wire ready
);
    assign source_ready=!valid || ready;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin data<=0;valid<=0;last<=0;end
        else if(source_ready) begin
            valid<=source_valid;
            if(source_valid) begin data<=source_data;last<=source_last;end
        end
endmodule
`default_nettype wire
