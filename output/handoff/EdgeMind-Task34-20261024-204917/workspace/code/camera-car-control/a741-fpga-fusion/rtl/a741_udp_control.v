`timescale 1ns/1ps
`default_nettype none
// Atomic EMC1 UDP -> existing UART protocol. UART stays internal to the FPGA.
// Session and monotonic request IDs reject delayed/replayed velocity datagrams.
module a741_udp_control #(parameter CLK_HZ=125000000,REPLY_TIMEOUT_MS=30)(
    input wire clk,rst_n,
    input wire [7:0] rx_data,input wire rx_valid,rx_last,rx_bad,
    output wire rx_ready,
    output reg [7:0] tx_data,output wire tx_valid,tx_first,tx_last,
    output wire [15:0] tx_length,input wire tx_ready,
    output wire motion_uart_rx,input wire motion_uart_tx,
    output reg [31:0] rejected,
    output wire [3:0] diagnostic_state
);
    localparam RECEIVE=0,CHECK_CRC=1,VALIDATE=2,SEND=3,WAIT_BUSY=4,
        WAIT_DONE=5,REPLY=6,MAKE_CRC=7,TRANSMIT=8;
    reg [3:0] state;
    assign diagnostic_state=state;
    reg [7:0] buffer[0:63];
    reg [6:0] count,index,packet_size,reply_count,reply_size,send_size;
    reg bad,session_valid;
    reg [31:0] session,number,wait_cycles;
    reg [15:0] crc;
    reg uart_start;
    wire uart_busy;
    wire [7:0] uart_byte;
    wire uart_valid,uart_error;
    wire [31:0] incoming_session={buffer[7],buffer[6],buffer[5],buffer[4]};
    wire [31:0] incoming_number={buffer[11],buffer[10],buffer[9],buffer[8]};
    wire signed [31:0] difference=incoming_number-number;
    wire same_session=session_valid && incoming_session==session;
    wire expects_reply=buffer[15]==8'h01 || buffer[15]==8'h02 || buffer[15]==8'h03 ||
        buffer[15]==8'h04 || buffer[15]==8'h20 || buffer[15]==8'h21 || buffer[15]==8'h30 || buffer[15]==8'h40 || buffer[15]==8'h41 || buffer[15]==8'h42 || buffer[15]==8'h43 || buffer[15]==8'h44 || buffer[15]==8'h46 ||
        (buffer[15]>=8'h50 && buffer[15]<=8'h57);
    wire known=expects_reply || buffer[15]==8'h05 || buffer[15]==8'h11 || buffer[15]==8'h45 || buffer[15]==8'h47;
    uart_tx #(.CLK_HZ(CLK_HZ)) sender(.clk(clk),.rstn(rst_n),.start(uart_start),
        .data(buffer[index]),.tx(motion_uart_rx),.busy(uart_busy));
    uart_rx #(.CLK_HZ(CLK_HZ)) receiver(.clk(clk),.rstn(rst_n),.rx(motion_uart_tx),
        .data(uart_byte),.valid(uart_valid),.framing_error(uart_error));
    assign rx_ready=state==RECEIVE;
    assign tx_valid=state==TRANSMIT;
    assign tx_first=state==TRANSMIT && index==0;
    assign tx_last=state==TRANSMIT && index==send_size-1;
    assign tx_length={9'd0,send_size};
    always @* tx_data=buffer[index];
    function [15:0] crc_byte;
        input [15:0] c;input [7:0] value;integer k;reg [15:0] v;
        begin
            v=c ^ {value,8'd0};
            for(k=0;k<8;k=k+1) v=v[15] ? (v<<1)^16'h1021 : v<<1;
            crc_byte=v;
        end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=RECEIVE;count<=0;index<=0;packet_size<=0;reply_count<=0;
            reply_size<=0;send_size<=0;bad<=0;session_valid<=0;session<=0;
            number<=0;wait_cycles<=0;crc<=16'hffff;uart_start<=0;rejected<=0;
        end else begin
            uart_start<=0;
            case(state)
                RECEIVE: if(rx_valid) begin
                    if(count<64) buffer[count]<=rx_data;
                    if(count<63) count<=count+1'b1;else bad<=1;
                    if(rx_bad) bad<=1;
                    if(rx_last) begin
                        packet_size<=count+1'b1;index<=0;crc<=16'hffff;
                        if(bad || rx_bad || count<23 || count>55) begin
                            count<=0;bad<=0;rejected<=rejected+1'b1;
                        end else state<=CHECK_CRC;
                    end
                end
                CHECK_CRC: begin
                    crc<=crc_byte(crc,buffer[index]);
                    if(index==packet_size-3) state<=VALIDATE;
                    else index<=index+1'b1;
                end
                VALIDATE: begin
                    if({buffer[packet_size-1],buffer[packet_size-2]}!=crc ||
                        {buffer[0],buffer[1],buffer[2],buffer[3]}!="EMC1" ||
                        buffer[12]!=8'haa || buffer[13]!=8'h55 || buffer[14]!=1 ||
                        buffer[16]>32 || packet_size!=24+buffer[16] || !known ||
                        (same_session ? difference<=0 : buffer[15]!=8'h04)) begin
                        state<=RECEIVE;count<=0;bad<=0;rejected<=rejected+1'b1;
                    end else begin
                        session<=incoming_session;number<=incoming_number;session_valid<=1;
                        index<=12;state<=SEND;
                    end
                end
                SEND: if(!uart_busy) begin uart_start<=1;state<=WAIT_BUSY;end
                WAIT_BUSY: if(uart_busy) state<=WAIT_DONE;
                WAIT_DONE: if(!uart_busy) begin
                    if(index==packet_size-3) begin
                        if(expects_reply) begin state<=REPLY;reply_count<=0;reply_size<=0;wait_cycles<=0;end
                        else begin state<=RECEIVE;count<=0;bad<=0;end
                    end else begin index<=index+1'b1;state<=SEND;end
                end
                REPLY: begin
                    wait_cycles<=wait_cycles+1'b1;
                    if(uart_error || wait_cycles>=CLK_HZ/1000*REPLY_TIMEOUT_MS) begin
                        state<=RECEIVE;count<=0;bad<=0;rejected<=rejected+1'b1;
                    end else if(uart_valid) begin
                        buffer[12+reply_count]<=uart_byte;
                        if(reply_count==4) reply_size<=10+uart_byte;
                        if((reply_count==0 && uart_byte!=8'haa) || (reply_count==1 && uart_byte!=8'h55) ||
                            (reply_count==4 && uart_byte>32) || reply_count>=42) begin
                            state<=RECEIVE;count<=0;bad<=0;rejected<=rejected+1'b1;
                        end else if(reply_size!=0 && reply_count==reply_size-1) begin
                            send_size<=12+reply_size+2;index<=0;crc<=16'hffff;state<=MAKE_CRC;
                        end else reply_count<=reply_count+1'b1;
                    end
                end
                MAKE_CRC: begin
                    crc<=crc_byte(crc,buffer[index]);
                    if(index==send_size-3) begin
                        buffer[0]<="E";buffer[1]<="M";buffer[2]<="C";buffer[3]<="1";
                        buffer[4]<=session[7:0];buffer[5]<=session[15:8];buffer[6]<=session[23:16];buffer[7]<=session[31:24];
                        buffer[8]<=number[7:0];buffer[9]<=number[15:8];buffer[10]<=number[23:16];buffer[11]<=number[31:24];
                        buffer[send_size-2]<=crc_byte(crc,buffer[index]) & 16'hff;
                        buffer[send_size-1]<=crc_byte(crc,buffer[index])>>8;
                        index<=0;state<=TRANSMIT;
                    end else index<=index+1'b1;
                end
                TRANSMIT: if(tx_ready) begin
                    if(index==send_size-1) begin state<=RECEIVE;count<=0;bad<=0;end
                    else index<=index+1'b1;
                end
                default:state<=RECEIVE;
            endcase
        end
endmodule
`default_nettype wire
