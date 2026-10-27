`timescale 1ns/1ps
`default_nettype none
// EMC1 keeps its wire format and both CRCs. The controller is in this same
// clock domain, so no internal UART or multiport packet buffer is required.
module a741_udp_direct #(parameter CLK_HZ=50000000,REPLY_TIMEOUT_MS=30)(
    input wire clk,rst_n,
    input wire [7:0] rx_data,input wire rx_valid,rx_last,rx_bad,output wire rx_ready,
    output reg [7:0] tx_data,output wire tx_valid,tx_first,tx_last,
    output wire [15:0] tx_length,input wire tx_ready,
    output reg command,output wire [7:0] kind,seq,output wire [15:0] ttl,
    output wire [255:0] payload,
    input wire reply_valid,input wire [7:0] reply_kind,reply_seq,reply_length,
    input wire [255:0] reply_payload,output wire reply_ready,
    output reg [31:0] rejected,output wire [3:0] diagnostic_state
);
    localparam RECEIVE=0,DISPATCH=1,WAIT_REPLY=2,TRANSMIT=3;
    localparam TIMEOUT=CLK_HZ/1000*REPLY_TIMEOUT_MS;
    reg [1:0] state;
    reg [5:0] count,index,size,send_size;
    reg bad,decoded,session_valid,parser_reset_n;
    reg [31:0] incoming_session,incoming_number,session,number;
    reg [$clog2(TIMEOUT+1)-1:0] wait_cycles;
    reg [7:0] previous,previous2,saved_kind,saved_seq;
    reg [255:0] send_payload;
    reg [15:0] rx_crc,outer_crc,inner_crc;
    wire parser_valid,parser_crc_error,parser_length_error;
    wire signed [31:0] difference=incoming_number-number;
    wire same_session=session_valid && incoming_session==session;
    wire expects_reply=kind!=8'h05 && kind!=8'h11;
    // Reset at every packet boundary, including malformed/truncated packets.
    // Parser output is held throughout dispatch and reply transmission.
    a741_protocol parser(.clk(clk),.rstn(rst_n && parser_reset_n),.rx_data(rx_data),
        .rx_valid(state==RECEIVE && rx_valid && count>=12 && {1'b0,count}<7'd22+size),
        .cmd_valid(parser_valid),.cmd_type(kind),.cmd_seq(seq),.cmd_ttl_ms(ttl),.cmd_payload(payload),
        .crc_error(parser_crc_error),.length_error(parser_length_error));
    function [15:0] crc_byte(input [15:0] old,input [7:0] data);
        reg [15:0] v;integer i;
        begin v=old^{data,8'd0};for(i=0;i<8;i=i+1) v=v[15] ? (v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    wire [15:0] rx_crc_next=crc_byte(rx_crc,previous2);
    assign rx_ready=state==RECEIVE;
    assign reply_ready=state==WAIT_REPLY;
    // Preserve the existing EMS1 diagnostic codes used by the host UI.
    assign diagnostic_state=state==RECEIVE ? 4'd0:state==DISPATCH ? 4'd2:state==WAIT_REPLY ? 4'd6:4'd8;
    assign tx_valid=state==TRANSMIT;
    assign tx_first=tx_valid && index==0;
    assign tx_last=tx_valid && index==6'd23+send_size;
    assign tx_length=16'd24+send_size;
    always @* begin
        tx_data=0;
        case(index)
            0:tx_data="E";1:tx_data="M";2:tx_data="C";3:tx_data="1";
            4,5,6,7:tx_data=session[index[1:0]*8+:8];
            8,9,10,11:tx_data=number[index[1:0]*8+:8];
            12:tx_data=8'haa;13:tx_data=8'h55;14:tx_data=1;
            15:tx_data=saved_kind;16:tx_data={2'd0,send_size};17:tx_data=saved_seq;
            18,19:tx_data=0;
            default:if(index<6'd20+send_size) tx_data=send_payload[7:0];
                else if(index==6'd20+send_size) tx_data=inner_crc[7:0];
                else if(index==6'd21+send_size) tx_data=inner_crc[15:8];
                else if(index==6'd22+send_size) tx_data=outer_crc[7:0];
                else tx_data=outer_crc[15:8];
        endcase
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=RECEIVE;count<=0;index<=0;size<=0;send_size<=0;bad<=0;decoded<=0;parser_reset_n<=0;
            session_valid<=0;incoming_session<=0;incoming_number<=0;session<=0;number<=0;
            wait_cycles<=0;previous<=0;previous2<=0;saved_kind<=0;saved_seq<=0;send_payload<=0;
            rx_crc<=16'hffff;outer_crc<=16'hffff;inner_crc<=16'hffff;command<=0;rejected<=0;
        end else begin
            command<=0;
            if(parser_valid) decoded<=1;
            if(parser_crc_error || parser_length_error) bad<=1;
            case(state)
                RECEIVE:begin
                    if(count==0) begin bad<=0;decoded<=0;rx_crc<=16'hffff;size<=0;end
                    if(rx_valid) begin
                        if(count==0) parser_reset_n<=1;
                        previous2<=previous;previous<=rx_data;
                        if(count>=2) rx_crc<=rx_crc_next;
                        if(count<63) count<=count+1'b1;else bad<=1;
                        if(rx_bad) bad<=1;
                        case(count)
                            0:if(rx_data!="E") bad<=1;
                            1:if(rx_data!="M") bad<=1;
                            2:if(rx_data!="C") bad<=1;
                            3:if(rx_data!="1") bad<=1;
                            4,5,6,7:incoming_session[count[1:0]*8+:8]<=rx_data;
                            8,9,10,11:incoming_number[count[1:0]*8+:8]<=rx_data;
                            12:if(rx_data!=8'haa) bad<=1;
                            13:if(rx_data!=8'h55) bad<=1;
                            14:if(rx_data!=1) bad<=1;
                            16:begin size<=rx_data[5:0];if(rx_data>32) bad<=1;end
                            default:begin end
                        endcase
                        if(rx_last) begin
                            if(bad || rx_bad || !decoded || parser_crc_error || parser_length_error ||
                                count<23 || {1'b0,count}!=7'd23+size || {rx_data,previous}!=rx_crc_next ||
                                (!same_session && kind!=8'h04) || (same_session && difference<=0)) begin
                                count<=0;bad<=0;decoded<=0;rx_crc<=16'hffff;rejected<=rejected+1'b1;parser_reset_n<=0;
                            end else begin
                                session<=incoming_session;number<=incoming_number;session_valid<=1;
                                command<=1;state<=DISPATCH;
                            end
                        end
                    end
                end
                DISPATCH:begin
                    wait_cycles<=0;
                    if(expects_reply) state<=WAIT_REPLY;
                    else begin state<=RECEIVE;count<=0;parser_reset_n<=0;end
                end
                WAIT_REPLY:begin
                    if(reply_valid && reply_length<=32) begin
                        saved_kind<=reply_kind;saved_seq<=reply_seq;send_size<=reply_length[5:0];
                        send_payload<=reply_payload;index<=0;outer_crc<=16'hffff;inner_crc<=16'hffff;
                        state<=TRANSMIT;
                    end else if(wait_cycles==TIMEOUT-1 || reply_valid) begin
                        state<=RECEIVE;count<=0;rejected<=rejected+1'b1;parser_reset_n<=0;
                    end else wait_cycles<=wait_cycles+1'b1;
                end
                TRANSMIT:if(tx_ready) begin
                    if(index>=14 && index<6'd20+send_size) inner_crc<=crc_byte(inner_crc,tx_data);
                    if(index<6'd22+send_size) outer_crc<=crc_byte(outer_crc,tx_data);
                    if(index>=20 && index<6'd20+send_size) send_payload<=send_payload>>8;
                    if(tx_last) begin state<=RECEIVE;count<=0;parser_reset_n<=0;end else index<=index+1'b1;
                end
                default:begin state<=RECEIVE;count<=0;end
            endcase
        end
endmodule
`default_nettype wire
