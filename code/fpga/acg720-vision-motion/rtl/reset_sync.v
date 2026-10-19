`timescale 1ns/1ps
`default_nettype none
module reset_sync(input wire clk, input wire async_n, output wire rst_n);
    (* ASYNC_REG="TRUE" *) reg [2:0] pipe;
    always @(posedge clk or negedge async_n)
        if (!async_n) pipe <= 0;
        else pipe <= {pipe[1:0],1'b1};
    assign rst_n=pipe[2];
endmodule
`default_nettype wire
