`timescale 1ns/1ps
`default_nettype none
// EMM1: magic,u32 request,u8 command,u8 size,payload,CRC16-CCITT (little endian).
// Parse and serialize bytes without a multiport packet buffer. The command
// pulse occurs only after the complete datagram passes length and CRC checks.
module a741_map_udp(
    input wire clk,rst_n,input wire [7:0] rx_data,input wire rx_valid,rx_last,rx_bad,output wire rx_ready,
    output reg [7:0] tx_data,output wire tx_valid,tx_last,output wire [15:0] tx_length,input wire tx_ready,
    output reg command,input wire command_ready,output reg [7:0] kind,output reg [255:0] payload,
    input wire reply_done,input wire [255:0] reply,output wire waiting
);
    localparam RECEIVE=0,VALIDATE=1,WAIT_REPLY=2,TRANSMIT=3;
    reg [1:0] state;
    reg [5:0] count,index,size;
    reg bad,discarding;reg [31:0] number;reg [255:0] send_payload;
    reg [7:0] previous,previous2;
    reg [15:0] crc;reg [18:0] wait_cycles;
    assign rx_ready=1;assign tx_valid=state==TRANSMIT;
    assign tx_last=tx_valid && index==43;assign tx_length=44;
    assign waiting=state==WAIT_REPLY;
    function [15:0] crc_byte(input [15:0] old,input [7:0] data);
        reg [15:0] v;integer i;begin v=old^{data,8'd0};for(i=0;i<8;i=i+1) v=v[15] ? (v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    wire [15:0] rx_crc_next=crc_byte(crc,previous2);
    always @* case(index)
        0:tx_data="E";1:tx_data="M";2:tx_data="M";3:tx_data="1";
        4,5,6,7:tx_data=number[index[1:0]*8+:8];
        8:tx_data=8'hd0;9:tx_data=32;
        42:tx_data=crc[7:0];43:tx_data=crc[15:8];
        default:tx_data=send_payload[7:0];
    endcase
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=RECEIVE;count<=0;index<=0;size<=0;bad<=0;discarding<=0;crc<=65535;command<=0;kind<=0;
            payload<=0;number<=0;send_payload<=0;previous<=0;previous2<=0;wait_cycles<=0;
        end else begin
            command<=0;
            // A packet that starts while busy must be discarded to its end,
            // even if the preceding reply finishes during that packet.
            if(rx_valid) begin
                if(rx_last) discarding<=0;
                else if(state!=RECEIVE) discarding<=1;
            end
            case(state)
                RECEIVE:begin
                    if(count==0) begin bad<=0;crc<=65535;payload<=0;end
                    if(rx_valid && !discarding) begin
                        previous2<=previous;previous<=rx_data;
                        if(count>=2) crc<=rx_crc_next;
                        if(count<63) count<=count+1'b1;else bad<=1;
                        if(rx_bad) bad<=1;
                        case(count)
                            0:if(rx_data!="E") bad<=1;
                            1:if(rx_data!="M") bad<=1;
                            2:if(rx_data!="M") bad<=1;
                            3:if(rx_data!="1") bad<=1;
                            4,5,6,7:number[count[1:0]*8+:8]<=rx_data;
                            8:kind<=rx_data;
                            9:begin size<=rx_data[5:0];if(rx_data>28) bad<=1;end
                            default:if(count>=10 && {1'b0,count}<7'd10+size && count<38)
                                payload[(count-6'd10)*8+:8]<=rx_data;
                        endcase
                        if(rx_last) begin
                            if(count<11 || count>39 || {1'b0,count}!=7'd11+size || bad || rx_bad ||
                                {rx_data,previous}!=rx_crc_next) begin count<=0;bad<=0;crc<=65535;end
                            else state<=VALIDATE;
                        end
                    end
                end
                VALIDATE:if(!command_ready || kind<8'h50 || kind>8'h52 ||
                    (kind==8'h50 && size!=1) || (kind==8'h52 && size!=4) ||
                    (kind==8'h51 && (size<4 || payload[7:0]>1 || payload[31:24]==0 || payload[31:24]>24 ||
                        {2'd0,size}!=(payload[7:0]==0 ? 8'd4:8'd4+payload[31:24])))) begin
                        state<=RECEIVE;count<=0;
                    end else begin command<=1;wait_cycles<=0;state<=WAIT_REPLY;end
                WAIT_REPLY:begin
                    wait_cycles<=wait_cycles+1'b1;
                    if(reply_done) begin send_payload<=reply;index<=0;crc<=65535;state<=TRANSMIT;end
                    else if(wait_cycles==500000) begin state<=RECEIVE;count<=0;end
                end
                TRANSMIT:if(tx_ready) begin
                    if(index<42) crc<=crc_byte(crc,tx_data);
                    if(index>=10 && index<42) send_payload<=send_payload>>8;
                    if(tx_last) begin state<=RECEIVE;count<=0;end else index<=index+1'b1;
                end
                default:begin state<=RECEIVE;count<=0;end
            endcase
        end
endmodule
`default_nettype wire
