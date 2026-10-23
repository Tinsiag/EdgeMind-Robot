`timescale 1ns/1ps
`default_nettype none
// EMM1: magic,u32 request,u8 command,u8 size,payload,CRC16-CCITT (little endian).
// This channel only transports stopped map operations, never motor commands.
module a741_map_udp(
    input wire clk,rst_n,input wire [7:0] rx_data,input wire rx_valid,rx_last,rx_bad,output wire rx_ready,
    output reg [7:0] tx_data,output wire tx_valid,tx_last,output wire [15:0] tx_length,input wire tx_ready,
    output reg command,input wire command_ready,output reg [7:0] kind,output reg [255:0] payload,
    input wire reply_done,input wire [255:0] reply,output wire waiting
);
    reg [7:0] buffer[0:63];reg [6:0] count,index,size;reg bad;reg [2:0] state;
    reg [15:0] crc;reg [31:0] wait_cycles;
    assign rx_ready=1;assign tx_valid=state==5;assign tx_last=index==43;assign tx_length=44;
    assign waiting=state==3;
    always @* tx_data=buffer[index];
    function [15:0] crc_byte(input [15:0] old,input [7:0] data);
        reg [15:0] v;integer i;begin v=old^{data,8'd0};for(i=0;i<8;i=i+1) v=v[15] ? (v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    integer n;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin count<=0;index<=0;size<=0;bad<=0;state<=0;crc<=65535;command<=0;kind<=0;payload<=0;wait_cycles<=0;end
        else begin
            command<=0;
            case(state)
                0:if(rx_valid) begin
                    if(count<64) buffer[count]<=rx_data;
                    if(count<63) count<=count+1'b1;else bad<=1;
                    if(rx_bad) bad<=1;
                    if(rx_last) begin
                        size<=count+1'b1;index<=0;crc<=65535;
                        if(count<11 || count>39 || bad || rx_bad) begin count<=0;bad<=0;end
                        else state<=1;
                    end
                end
                1:begin crc<=crc_byte(crc,buffer[index]);if(index==size-3) state<=2;else index<=index+1'b1;end
                2:if({buffer[3],buffer[2],buffer[1],buffer[0]}!=32'h314d4d45 || {buffer[size-1],buffer[size-2]}!=crc ||
                    buffer[9]+12!=size || buffer[8]<8'h50 || buffer[8]>8'h52 || !command_ready ||
                    (buffer[8]==8'h50 && buffer[9]!=1) || (buffer[8]==8'h52 && buffer[9]!=4) ||
                    (buffer[8]==8'h51 && (buffer[9]<4 || buffer[10]>1 || buffer[13]==0 || buffer[13]>24 ||
                        buffer[9]!=(buffer[10]==0 ? 4:4+buffer[13])))) begin state<=0;count<=0;bad<=0;end
                    else begin
                        kind<=buffer[8];payload<=0;for(n=0;n<28;n=n+1) if(n<buffer[9]) payload[n*8+:8]<=buffer[10+n];
                        command<=1;wait_cycles<=0;state<=3;
                    end
                3:begin
                    wait_cycles<=wait_cycles+1'b1;
                    if(reply_done) begin
                        buffer[8]<=8'hd0;buffer[9]<=32;
                        for(n=0;n<32;n=n+1) buffer[10+n]<=reply[n*8+:8];
                        index<=0;crc<=65535;state<=4;
                    end else if(wait_cycles==500000) begin state<=0;count<=0;bad<=0;end
                end
                4:begin
                    crc<=crc_byte(crc,buffer[index]);
                    if(index==41) begin buffer[42]<=crc_byte(crc,buffer[index]);buffer[43]<=crc_byte(crc,buffer[index])>>8;index<=0;state<=5;end
                    else index<=index+1'b1;
                end
                5:if(tx_ready) begin if(index==43) begin state<=0;count<=0;bad<=0;end else index<=index+1'b1;end
                default:state<=0;
            endcase
        end
endmodule
`default_nettype wire
