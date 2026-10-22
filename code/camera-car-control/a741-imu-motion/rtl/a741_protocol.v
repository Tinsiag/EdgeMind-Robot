`timescale 1ns/1ps
`default_nettype none
module a741_protocol(
    input wire clk,
    input wire rstn,
    input wire [7:0] rx_data,
    input wire rx_valid,
    output reg cmd_valid,
    output reg [7:0] cmd_type,
    output reg [7:0] cmd_seq,
    output reg [15:0] cmd_ttl_ms,
    output reg [255:0] cmd_payload,
    output reg crc_error,
    output reg length_error
);
    localparam S_SYNC1=0, S_SYNC2=1, S_VER=2, S_TYPE=3, S_LEN=4, S_SEQ=5,
               S_TTL0=6, S_TTL1=7, S_PAYLOAD=8, S_CRC0=9, S_CRC1=10;
    reg [3:0] state;
    reg [7:0] version, length, payload_index, crc_lo;
    reg [15:0] crc, received_crc;
    reg [7:0] payload [0:31];
    integer i;
    function [15:0] crc16_byte;
        input [15:0] c;
        input [7:0] d;
        integer k;
        reg [15:0] x;
        begin x=c; for(k=0;k<8;k=k+1) x = (x[15]^d[7-k]) ? ((x<<1)^16'h1021) : (x<<1); crc16_byte=x; end
    endfunction
    function valid_length;
        input [7:0] kind,size;
        begin
            case(kind)
                8'h01,8'h02,8'h03,8'h04,8'h05,8'h20,8'h21,8'h40,8'h41,8'h43: valid_length=size==0;
                8'h11,8'h45:valid_length=size==8;
                8'h47:valid_length=size==10;
                8'h30:valid_length=size==5;
                8'h42:valid_length=size==6;
                8'h44:valid_length=size==4;
                8'h46:valid_length=size==2;
                default:valid_length=0;
            endcase
        end
    endfunction
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin state<=S_SYNC1; version<=0; length<=0; payload_index<=0; crc<=16'hffff;
            received_crc<=0; cmd_valid<=0; cmd_type<=0; cmd_seq<=0; cmd_ttl_ms<=0; cmd_payload<=0;
            crc_error<=0; length_error<=0; crc_lo<=0; end
        else begin
            cmd_valid<=0; crc_error<=0; length_error<=0;
            if (rx_valid) begin
                case(state)
                    S_SYNC1: state <= (rx_data==8'hAA) ? S_SYNC2 : S_SYNC1;
                    S_SYNC2: state <= (rx_data==8'h55) ? S_VER : S_SYNC1;
                    S_VER: begin version<=rx_data; crc<=crc16_byte(16'hffff,rx_data); state<=S_TYPE; end
                    S_TYPE: begin cmd_type<=rx_data; crc<=crc16_byte(crc,rx_data); state<=S_LEN; end
                    S_LEN: begin length<=rx_data; crc<=crc16_byte(crc,rx_data); if(rx_data>32) begin length_error<=1; state<=S_SYNC1; end else state<=S_SEQ; end
                    S_SEQ: begin cmd_seq<=rx_data; crc<=crc16_byte(crc,rx_data); state<=S_TTL0; end
                    S_TTL0: begin cmd_ttl_ms[7:0]<=rx_data; crc<=crc16_byte(crc,rx_data); state<=S_TTL1; end
                    S_TTL1: begin cmd_ttl_ms[15:8]<=rx_data; crc<=crc16_byte(crc,rx_data); payload_index<=0; state <= (length==0) ? S_CRC0 : S_PAYLOAD; end
                    S_PAYLOAD: begin payload[payload_index]<=rx_data; cmd_payload[payload_index*8 +: 8]<=rx_data; crc<=crc16_byte(crc,rx_data); if(payload_index==length-1) state<=S_CRC0; else payload_index<=payload_index+1'b1; end
                    S_CRC0: begin crc_lo<=rx_data; state<=S_CRC1; end
                    S_CRC1: begin
                        received_crc={rx_data,crc_lo}; state<=S_SYNC1;
                        if (version != 1 || !valid_length(cmd_type,length)) length_error<=1;
                        else if ({rx_data,crc_lo} != crc) crc_error<=1;
                        else begin cmd_valid<=1; end
                    end
                    default: state<=S_SYNC1;
                endcase
            end
        end
    end
endmodule
`default_nettype wire
