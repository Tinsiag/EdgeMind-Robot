`timescale 1ns/1ps
`default_nettype none
module vision_packet_tx #(parameter CLK_HZ=50000000,BAUD=115200)(
    input wire clk,rst_n,request,input wire [7:0] kind,seq,length,
    input wire [255:0] payload,output wire ready,tx
);
    reg [7:0] bytes[0:41];reg [7:0] index,total,crc_index;
    reg [1:0] state;reg [15:0] crc;
    reg tx_start;reg [7:0] tx_data;wire tx_busy;
    integer i;
    assign ready=state==0;
    uart_tx #(.CLK_HZ(CLK_HZ),.BAUD(BAUD)) uart(.clk(clk),.rstn(rst_n),.start(tx_start),.data(tx_data),.busy(tx_busy),.tx(tx));
    function [15:0] crc_byte;
        input [15:0] c;input [7:0] d;reg [15:0] v;integer k;
        begin v=c;for(k=0;k<8;k=k+1) v=(v[15]^d[7-k])?((v<<1)^16'h1021):(v<<1);crc_byte=v;end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin index<=0;total<=0;crc_index<=0;state<=0;crc<=16'hffff;tx_start<=0;tx_data<=0;end
        else begin
            tx_start<=0;
            case(state)
                0: if(request && length<=32) begin
                    bytes[0]<=8'haa;bytes[1]<=8'h55;bytes[2]<=1;bytes[3]<=kind;bytes[4]<=length;bytes[5]<=seq;bytes[6]<=0;bytes[7]<=0;
                    for(i=0;i<32;i=i+1) bytes[8+i]<=payload[i*8+:8];
                    total<=8'd10+length;crc_index<=2;crc<=16'hffff;state<=1;
                end
                1: if(crc_index<total-2) begin crc<=crc_byte(crc,bytes[crc_index]);crc_index<=crc_index+1'b1;end
                   else begin bytes[total-2]<=crc[7:0];bytes[total-1]<=crc[15:8];index<=0;state<=2;end
                2: if(!tx_busy && !tx_start) begin
                    if(index==total) state<=0;
                    else begin tx_data<=bytes[index];tx_start<=1;index<=index+1'b1;end
                end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
