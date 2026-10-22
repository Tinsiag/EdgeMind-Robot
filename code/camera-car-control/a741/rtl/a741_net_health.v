`timescale 1ns/1ps
`default_nettype none
// MAC status pulses are already synchronized into the logic clock domain.
module a741_net_health(
    input wire clk,rst_n,rx_good_frame,rx_bad_fcs,rx_bad_frame,rx_overflow,
    output reg [127:0] counters,
    output wire [7:0] status
);
    reg [3:0] good_mod16,bad_saturated;
    assign status={bad_saturated,good_mod16};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin good_mod16<=0;bad_saturated<=0;counters<=0;end
        else begin
            if(rx_good_frame) counters[31:0]<=counters[31:0]+1'b1;
            if(rx_bad_fcs) counters[63:32]<=counters[63:32]+1'b1;
            if(rx_bad_frame) counters[95:64]<=counters[95:64]+1'b1;
            if(rx_overflow) counters[127:96]<=counters[127:96]+1'b1;
            if(rx_good_frame) good_mod16<=good_mod16+1'b1;
            if(rx_bad_fcs && bad_saturated!=15) bad_saturated<=bad_saturated+1'b1;
        end
endmodule
`default_nettype wire
