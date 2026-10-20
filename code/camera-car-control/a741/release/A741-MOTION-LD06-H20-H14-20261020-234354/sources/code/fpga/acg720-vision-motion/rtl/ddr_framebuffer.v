`timescale 1ns/1ps
`default_nettype none
// Native GW DDR user port: app_addr counts x16 words, a 128-bit beat is +8.
// The wrapper must configure BL8, 128-bit UI, and ordered read responses.
// Source tokens: 01 start, 00 RGB565 pixel, 10 good end, 11 bad end.
module ddr_framebuffer #(parameter WIDTH=800,HEIGHT=480)(
    input wire clk,rst_n,calibrated,
    input wire [17:0] source_data,input wire source_empty,output wire source_pop,
    input wire display_blank,display_flush_done,
    output reg display_flush,output wire [127:0] display_data,
    output wire display_push,input wire display_full,
    output wire [27:0] app_addr,output wire [2:0] app_cmd,output wire app_en,
    input wire app_rdy,output wire [127:0] app_wdf_data,
    output wire app_wdf_wren,app_wdf_end,input wire app_wdf_rdy,
    input wire [127:0] app_rd_data,input wire app_rd_data_valid,
    output reg frame_available,output reg error,output reg [31:0] dropped_frames,
    output reg read_bank,write_bank
);
    localparam PIXELS=WIDTH*HEIGHT,BLOCKS=PIXELS/8;
    // 1 Mi x16 words per bank (2 MiB), enough for 800x480 RGB565.
    localparam [27:0] BANK_STRIDE=28'h0100000;
    reg capturing,pending_frame,pending_bank,first_frame;
    reg [31:0] pixels,write_blocks,read_blocks;
    reg [2:0] packed_pixels;
    reg [127:0] packed_data,write_data;
    reg write_pending,cmd_sent,data_sent,read_pending;
    reg [27:0] write_addr,read_addr;
    reg read_stream,blank_wait,flush_wait,prefer_read;
    reg [31:0] read_outstanding;
    wire write_complete=write_pending && (cmd_sent || (app_en && app_cmd==0 && app_rdy)) &&
        (data_sent || (app_wdf_wren && app_wdf_rdy));
    wire can_read=frame_available && read_stream && !display_blank && !blank_wait && !flush_wait && read_blocks<BLOCKS && !read_pending &&
        read_outstanding==0 && !display_full;
    wire [27:0] read_offset={read_blocks[24:0],3'b000};
    wire [27:0] write_offset={write_blocks[24:0],3'b000};
    // One DDR read outstanding: reserve its entire return slot before issue.
    wire select_read=read_pending || (!write_pending && can_read && (source_empty || prefer_read));
    assign app_en=calibrated && (select_read ? (read_pending || can_read):write_pending && !cmd_sent);
    assign app_cmd=select_read ? 3'd1:3'd0;
    assign app_addr=select_read ? (read_pending ? read_addr:(read_bank ? BANK_STRIDE:28'd0)+read_offset):write_addr;
    assign app_wdf_data=write_data;
    assign app_wdf_wren=calibrated && write_pending && !data_sent;
    assign app_wdf_end=app_wdf_wren;
    assign display_data=app_rd_data;
    assign display_push=app_rd_data_valid && read_outstanding!=0 && !display_flush;
    assign source_pop=calibrated && !source_empty && !write_pending && !read_pending && !blank_wait && !flush_wait && !select_read;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            capturing<=0;pending_frame<=0;pending_bank<=0;first_frame<=1;
            pixels<=0;write_blocks<=0;read_blocks<=0;packed_pixels<=0;packed_data<=0;
            write_data<=0;write_pending<=0;cmd_sent<=0;data_sent<=0;read_pending<=0;
            write_addr<=0;read_addr<=0;read_stream<=0;blank_wait<=0;flush_wait<=0;prefer_read<=1;
            read_outstanding<=0;display_flush<=0;frame_available<=0;error<=0;
            dropped_frames<=0;read_bank<=0;write_bank<=1;
        end else begin
            display_flush<=0;
            if(!calibrated) begin
                capturing<=0;pending_frame<=0;write_pending<=0;read_pending<=0;
                frame_available<=0;read_stream<=0;read_outstanding<=0;
                if(frame_available) error<=1;
            end else begin
                if(app_en && app_cmd==0 && app_rdy) cmd_sent<=1;
                if(app_wdf_wren && app_wdf_rdy) data_sent<=1;
                if(write_complete) begin write_pending<=0;cmd_sent<=0;data_sent<=0;write_blocks<=write_blocks+1'b1;end
                if(select_read && app_en) begin
                    if(app_rdy) begin read_pending<=0;read_blocks<=read_blocks+1'b1;read_outstanding<=1;prefer_read<=0;end
                    else begin read_pending<=1;read_addr<=app_addr;end
                end
                if(app_rd_data_valid) begin
                    if(read_outstanding==0 || display_full) error<=1;
                    read_outstanding<=0;
                end
                if(source_pop) begin
                    prefer_read<=1;
                    case(source_data[17:16])
                        2'b01: begin
                            pixels<=0;packed_pixels<=0;packed_data<=0;write_blocks<=0;
                            capturing<=!pending_frame && !blank_wait;
                            if(pending_frame) dropped_frames<=dropped_frames+1'b1;
                        end
                        2'b00: if(capturing) begin
                            packed_data<={source_data[15:0],packed_data[127:16]};
                            pixels<=pixels+1'b1;packed_pixels<=packed_pixels+1'b1;
                            if(pixels>=PIXELS) capturing<=0;
                            else if(packed_pixels==7) begin
                                write_data<={source_data[15:0],packed_data[127:16]};
                                write_addr<=(write_bank ? BANK_STRIDE:28'd0)+write_offset;
                                write_pending<=1;cmd_sent<=0;data_sent<=0;
                            end
                        end
                        2'b10,2'b11: begin
                            capturing<=0;
                            if(capturing && source_data[17:16]==2'b10 && pixels==PIXELS &&
                               packed_pixels==0 && write_blocks==BLOCKS) begin pending_frame<=1;pending_bank<=write_bank;end
                            else if(capturing) dropped_frames<=dropped_frames+1'b1;
                        end
                    endcase
                end
                if(display_blank) begin blank_wait<=1;read_stream<=0;end
                // Drain any accepted old read before flushing and changing banks.
                if(blank_wait && !read_pending && read_outstanding==0 && !write_pending) begin
                    display_flush<=1;blank_wait<=0;flush_wait<=1;read_blocks<=0;
                    if(pending_frame) begin
                        read_bank<=pending_bank;write_bank<=~pending_bank;
                        pending_frame<=0;frame_available<=1;first_frame<=0;
                    end
                    read_stream<=0;
                end
                if(flush_wait && display_flush_done) begin flush_wait<=0;read_stream<=frame_available;end
            end
        end
endmodule
`default_nettype wire
