`timescale 1ns/1ps
`default_nettype none
// Input tokens: 00=pixel, 01=start, 10=good end, 11=bad end.
// UDP payload only. The platform MAC supplies IPv4/UDP/FCS and validates RX.
module video_udp_packetizer #(
    parameter WIDTH=800, HEIGHT=480, CHUNK_PIXELS=320
)(
    input wire clk,rst_n,
    input wire [17:0] token_data,
    input wire token_empty,
    output wire token_read,
    output reg [7:0] udp_data,
    output wire udp_valid,udp_start,udp_last,
    output wire [15:0] udp_length,
    input wire udp_ready
);
    localparam COLLECT=0, HEADER=1, PIXELS=2;
    reg [1:0] state;
    reg [15:0] memory [0:CHUNK_PIXELS-1];
    localparam MEM_ADDR_BITS=(CHUNK_PIXELS<2) ? 1 : $clog2(CHUNK_PIXELS);
    reg [15:0] pixel_q;
    reg [31:0] frame_id,total;
    reg [15:0] row,column,chunk_start,used,send_count,flags;
    reg [15:0] send_row,send_offset,byte_index;
    reg [4:0] header_index;
    reg active;
    wire [1:0] kind=token_data[17:16];
    wire [MEM_ADDR_BITS-1:0] read_address=state==PIXELS ?
        (byte_index>>1)+(udp_ready && byte_index[0]) : 0;
    // Prefetch the next word when its preceding low byte is accepted.
    always @(posedge clk) pixel_q<=memory[read_address];
    always @(posedge clk)
        if(rst_n && state==COLLECT && !token_empty && kind==0 && active && row<HEIGHT && column<WIDTH)
            memory[used[MEM_ADDR_BITS-1:0]]<=token_data[15:0];
    assign token_read=state==COLLECT && !token_empty;
    assign udp_valid=state!=COLLECT;
    assign udp_start=state==HEADER && header_index==0;
    assign udp_last=(state==HEADER && header_index==19 && send_count==0) ||
                    (state==PIXELS && byte_index==send_count*2-1);
    assign udp_length=20+send_count*2;
    function [7:0] header_byte;
        input [4:0] index;
        begin
            case(index)
                0:header_byte="E"; 1:header_byte="M"; 2:header_byte="V"; 3:header_byte="1";
                4:header_byte=frame_id[7:0]; 5:header_byte=frame_id[15:8];
                6:header_byte=frame_id[23:16]; 7:header_byte=frame_id[31:24];
                8:header_byte=WIDTH & 255; 9:header_byte=(WIDTH>>8) & 255;
                10:header_byte=HEIGHT & 255; 11:header_byte=(HEIGHT>>8) & 255;
                12:header_byte=send_row[7:0]; 13:header_byte=send_row[15:8];
                14:header_byte=send_offset[7:0]; 15:header_byte=send_offset[15:8];
                16:header_byte=send_count[7:0]; 17:header_byte=send_count[15:8];
                18:header_byte=flags[7:0]; 19:header_byte=flags[15:8];
                default:header_byte=0;
            endcase
        end
    endfunction
    always @* begin
        udp_data=0;
        if(state==HEADER) udp_data=header_byte(header_index);
        else if(state==PIXELS)
            udp_data=byte_index[0] ? pixel_q[7:0] : pixel_q[15:8];
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=COLLECT;frame_id<=0;total<=0;row<=0;column<=0;used<=0;
            send_count<=0;flags<=0;header_index<=0;byte_index<=0;
            send_row<=0;send_offset<=0;chunk_start<=0;active<=0;
        end else case(state)
            COLLECT: if(!token_empty) begin
                if(kind==2'b01) begin
                    frame_id<=frame_id+1'b1;total<=0;row<=0;column<=0;
                    used<=0;chunk_start<=0;active<=1;
                end else if(kind==2'b00 && active) begin
                    if(row<HEIGHT && column<WIDTH) begin
                        used<=used+1'b1;total<=total+1'b1;
                        if(used==0) chunk_start<=column;
                        if(used==CHUNK_PIXELS-1 || column==WIDTH-1) begin
                            send_row<=row;send_offset<=used==0 ? column : chunk_start;
                            send_count<=used+1'b1;flags<=0;header_index<=0;state<=HEADER;
                        end
                        if(column==WIDTH-1) begin column<=0;row<=row+1'b1;end
                        else column<=column+1'b1;
                    end else active<=0;
                end else if(kind[1]) begin
                    send_count<=0;send_row<=0;send_offset<=0;
                    flags<=(kind==2'b10 && active && total==WIDTH*HEIGHT && used==0) ? 1 : 2;
                    header_index<=0;state<=HEADER;active<=0;used<=0;
                end
            end
            HEADER: if(udp_ready) begin
                if(header_index==19) begin
                    if(send_count==0) state<=COLLECT;
                    else begin state<=PIXELS;byte_index<=0;end
                end else header_index<=header_index+1'b1;
            end
            PIXELS: if(udp_ready) begin
                if(byte_index==send_count*2-1) begin state<=COLLECT;used<=0;end
                else byte_index<=byte_index+1'b1;
            end
            default:state<=COLLECT;
        endcase
endmodule
`default_nettype wire
