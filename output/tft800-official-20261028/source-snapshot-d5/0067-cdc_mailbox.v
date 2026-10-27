`timescale 1ns/1ps
`default_nettype none
// Bundled-data handshake. Both domains must receive the same asynchronous reset.
// The source holds payload until the destination has acknowledged its request.
module cdc_mailbox #(parameter WIDTH=64)(
    input wire src_clk, src_rst_n, src_valid, input wire [WIDTH-1:0] src_data,
    output wire src_ready,
    input wire dst_clk, dst_rst_n, output reg dst_valid,
    output reg [WIDTH-1:0] dst_data
);
    reg [WIDTH-1:0] held;
    reg req, ack;
    (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync, req_sync;
    assign src_ready=(req==ack_sync[1]);
    always @(posedge src_clk or negedge src_rst_n)
        if(!src_rst_n) begin held<=0; req<=0; ack_sync<=0; end
        else begin
            ack_sync<={ack_sync[0],ack};
            if(src_valid && src_ready) begin held<=src_data; req<=~req; end
        end
    always @(posedge dst_clk or negedge dst_rst_n)
        if(!dst_rst_n) begin req_sync<=0; ack<=0; dst_valid<=0; dst_data<=0; end
        else begin
            req_sync<={req_sync[0],req}; dst_valid<=0;
            if(req_sync[1]!=ack) begin dst_data<=held; dst_valid<=1; ack<=req_sync[1]; end
        end
endmodule
`default_nettype wire
