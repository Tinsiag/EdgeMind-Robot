`timescale 1ns/1ps
`default_nettype none
module motion_status_tx #(
    parameter integer CLK_HZ=50000000,
    parameter integer BAUD=115200
)(
    input wire clk,
    input wire rstn,
    input wire request,
    input wire capabilities_request,
    input wire [7:0] request_seq,
    input wire [7:0] state_code,
    input wire [15:0] faults,
    input wire signed [31:0] left_count,
    input wire signed [31:0] right_count,
    input wire signed [31:0] left_speed,
    input wire signed [31:0] right_speed,
    input wire [15:0] left_pwm,
    input wire [15:0] right_pwm,
    input wire [15:0] command_age,
    output wire tx
);
    reg tx_start; reg [7:0] tx_data; wire tx_busy;
    uart_tx #(.CLK_HZ(CLK_HZ),.BAUD(BAUD)) u_tx(.clk(clk),.rstn(rstn),.start(tx_start),.data(tx_data),.tx(tx),.busy(tx_busy));
    reg [7:0] frame [0:34]; reg [7:0] index, total; reg sending;
    integer i; reg [15:0] crc;
    function [15:0] crc16_byte;
        input [15:0] c; input [7:0] d; integer k; reg [15:0] x;
        begin x=c; for(k=0;k<8;k=k+1) x=(x[15]^d[7-k])?((x<<1)^16'h1021):(x<<1); crc16_byte=x; end
    endfunction
    always @(posedge clk or negedge rstn) begin
        if(!rstn) begin tx_start<=0; tx_data<=0; index<=0; total<=0; sending<=0; end
        else begin
            tx_start<=0;
            if(request && !sending) begin
                frame[0]=8'hAA; frame[1]=8'h55; frame[2]=1; frame[3]=8'h80; frame[4]=25; frame[5]=request_seq; frame[6]=0; frame[7]=0;
                frame[8]=state_code; frame[9]=faults[7:0]; frame[10]=faults[15:8];
                frame[11]=left_count[7:0]; frame[12]=left_count[15:8]; frame[13]=left_count[23:16]; frame[14]=left_count[31:24];
                frame[15]=right_count[7:0]; frame[16]=right_count[15:8]; frame[17]=right_count[23:16]; frame[18]=right_count[31:24];
                frame[19]=left_speed[7:0]; frame[20]=left_speed[15:8]; frame[21]=left_speed[23:16]; frame[22]=left_speed[31:24];
                frame[23]=right_speed[7:0]; frame[24]=right_speed[15:8]; frame[25]=right_speed[23:16]; frame[26]=right_speed[31:24];
                frame[27]=left_pwm[7:0]; frame[28]=left_pwm[15:8]; frame[29]=right_pwm[7:0]; frame[30]=right_pwm[15:8];
                frame[31]=command_age[7:0]; frame[32]=command_age[15:8];
                if(capabilities_request === 1'b1) begin
                    // Same EVM1 envelope as vision firmware; only bridge-fixed
                    // flag is set, so the host must NOT enable vision controls.
                    frame[3]=8'hc0;frame[4]=8;
                    frame[8]=8'h45;frame[9]=8'h56;frame[10]=8'h4d;frame[11]=8'h31;
                    frame[12]=1;frame[13]=0;frame[14]=8'h90;frame[15]=1; // flags=1, max=400
                    crc=16'hffff;for(i=2;i<16;i=i+1) crc=crc16_byte(crc,frame[i]);
                    frame[16]=crc[7:0];frame[17]=crc[15:8];total<=18;
                end else begin
                    crc=16'hffff; for(i=2;i<33;i=i+1) crc=crc16_byte(crc,frame[i]);
                    frame[33]=crc[7:0]; frame[34]=crc[15:8]; total<=35;
                end
                index<=1; tx_data<=8'hAA; tx_start<=1; sending<=1;
            // tx_start is registered: UART consumes it on the next edge.
            // Wait for that acceptance before advancing to another byte.
            end else if(sending && !tx_busy && !tx_start) begin
                if(index<total) begin tx_data<=frame[index]; tx_start<=1; index<=index+1'b1; end
                else sending<=0;
            end
        end
    end
endmodule
`default_nettype wire
