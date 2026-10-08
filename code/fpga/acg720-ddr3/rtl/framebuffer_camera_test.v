// Camera-frame CRC32 test of the passed chapter 38 FIFO/DDR path.
// The official read FIFO is FWFT=true, OUTPUT_REG=false: compare Q on pop.
module framebuffer_camera_test #(
    parameter FRAME_WIDTH = 800,
    parameter FRAME_HEIGHT = 480,
    parameter UI_TIMEOUT_CYCLES = 500000000
)(
    input reset_n,
    input wr_clk,
    input ui_clk,
    input rd_clk,
    input ui_reset,
    input calibrated,
    input source_valid,
    input [15:0] source_pixel,
    input capture_good,
    output [31:0] source_crc,
    output [31:0] read_crc,
    input write_fifo_full,
    output write_enable,
    output reg input_frame_done,
    output reg input_overflow,
    input write_fire,
    input read_fire,
    input [27:0] command_address,
    input read_data_valid,
    output read_enable,
    output reg write_frame_done,
    output reg ui_error,
    output reg timeout_error,
    input read_fifo_empty,
    input [15:0] read_pixel,
    output read_pop,
    output reg compare_done,
    output reg compare_error,
    output compare_pass,
    output reg [18:0] checked_pixels,
    output reg [18:0] first_error_pixel,
    output reg [15:0] first_error_expected,
    output reg [15:0] first_error_actual
);
    localparam PIXELS = FRAME_WIDTH * FRAME_HEIGHT;
    localparam BLOCKS = PIXELS / 8;
    reg [1:0] wr_cal;
    reg [1:0] rd_cal;
    reg [1:0] rd_written;
    reg [1:0] done_ui;
    reg [18:0] input_pixels;
    reg [18:0] writes;
    reg [18:0] reads;
    reg [18:0] returns;
    localparam TIMEOUT_WIDTH = $clog2(UI_TIMEOUT_CYCLES + 1);
    reg [TIMEOUT_WIDTH-1:0] timeout_count;
    reg [31:0] source_crc_state, read_crc_state;
    (* ASYNC_REG = "TRUE" *) reg [1:0] capture_ui, capture_rd, input_done_rd;
    // The CRC bus is stable before capture_good is asserted at frame end.
    // Two-stage ready synchronizers establish a bundled-data handshake.
    assign source_crc = ~source_crc_state;
    assign read_crc = ~read_crc_state;
    function [31:0] crc16;
        input [31:0] previous_crc;
        input [15:0] pixel;
        reg [31:0] current_crc;
        reg [7:0] octet;
        integer byte_index, bit_index;
        begin
            current_crc = previous_crc;
            for (byte_index=0; byte_index<2; byte_index=byte_index+1) begin
                octet = byte_index == 0 ? pixel[15:8] : pixel[7:0];
                current_crc = current_crc ^ octet;
                for (bit_index=0; bit_index<8; bit_index=bit_index+1)
                    current_crc = current_crc[0] ?
                        (current_crc >> 1) ^ 32'hedb88320 : (current_crc >> 1);
            end
            crc16 = current_crc;
        end
    endfunction
    reg [11:0] read_column;
    wire [7:0] expected_high = {read_column[6:0], 1'b1};
    wire [7:0] expected_low = {read_column[6:0], 1'b0} + 8'd2;
    wire [15:0] expected_pixel = {expected_high, expected_low};

    assign write_enable = wr_cal[1] && source_valid && !input_frame_done
                        && !write_fifo_full;
    assign read_enable = write_frame_done && capture_ui[1] && (reads < BLOCKS)
                       && !ui_error && !timeout_error;
    assign read_pop = rd_cal[1] && rd_written[1] && capture_rd[1] && input_done_rd[1] && !read_fifo_empty
                    && !compare_done;
    assign compare_pass = compare_done && !compare_error;

    always @(posedge wr_clk or negedge reset_n) begin
        if (!reset_n) begin
            wr_cal <= 0;
            input_pixels <= 0; source_crc_state <= 32'hffffffff;
            input_frame_done <= 0;
            input_overflow <= 0;
        end else begin
            wr_cal <= {wr_cal[0], calibrated};
            if (!wr_cal[1]) begin
                input_pixels <= 0; source_crc_state <= 32'hffffffff;
                input_frame_done <= 0;
                input_overflow <= 0;
            end else if (source_valid && !input_frame_done) begin
                if (write_fifo_full)
                    input_overflow <= 1;
                if (write_enable) begin
                    input_pixels <= input_pixels + 1'b1;
                    source_crc_state <= crc16(source_crc_state, source_pixel);
                    if (input_pixels == PIXELS - 1)
                        input_frame_done <= 1;
                end
            end
        end
    end

    always @(posedge ui_clk or negedge reset_n) begin
        if (!reset_n) begin
            writes <= 0; reads <= 0; returns <= 0;
            write_frame_done <= 0; ui_error <= 0;
            timeout_count <= 0; timeout_error <= 0;
            done_ui <= 0; capture_ui <= 0;
        end else if (ui_reset || !calibrated) begin
            writes <= 0; reads <= 0; returns <= 0;
            write_frame_done <= 0; ui_error <= 0;
            timeout_count <= 0; timeout_error <= 0;
            done_ui <= 0; capture_ui <= 0;
        end else begin
            done_ui <= {done_ui[0], compare_done};
            capture_ui <= {capture_ui[0], capture_good};
            if (write_fire) begin
                if (writes >= BLOCKS || command_address != (writes << 3))
                    ui_error <= 1;
                if (writes < BLOCKS) begin
                    writes <= writes + 1'b1;
                    if (writes == BLOCKS - 1)
                        write_frame_done <= 1;
                end
            end
            if (read_fire) begin
                if (!write_frame_done || reads >= BLOCKS ||
                    command_address != (reads << 3))
                    ui_error <= 1;
                if (reads < BLOCKS)
                    reads <= reads + 1'b1;
            end
            if (read_data_valid) begin
                if (returns >= BLOCKS || (returns >= reads && !read_fire))
                    ui_error <= 1;
                if (returns < BLOCKS)
                    returns <= returns + 1'b1;
            end
            if (!done_ui[1] && !timeout_error) begin
                if (timeout_count == UI_TIMEOUT_CYCLES - 1)
                    timeout_error <= 1;
                else
                    timeout_count <= timeout_count + 1'b1;
            end
        end
    end

    always @(posedge rd_clk or negedge reset_n) begin
        if (!reset_n) begin
            rd_cal <= 0; rd_written <= 0;
            capture_rd <= 0; input_done_rd <= 0; read_crc_state <= 32'hffffffff;
            read_column <= 0; checked_pixels <= 0;
            compare_done <= 0; compare_error <= 0;
            first_error_pixel <= 0;
            first_error_expected <= 0; first_error_actual <= 0;
        end else begin
            rd_cal <= {rd_cal[0], calibrated};
            rd_written <= {rd_written[0], write_frame_done};
            capture_rd <= {capture_rd[0], capture_good};
            input_done_rd <= {input_done_rd[0], input_frame_done};
            if (!rd_cal[1]) begin
                read_crc_state <= 32'hffffffff;
                read_column <= 0; checked_pixels <= 0;
                compare_done <= 0; compare_error <= 0;
                first_error_pixel <= 0;
                first_error_expected <= 0; first_error_actual <= 0;
            end else if (read_pop) begin
                read_crc_state <= crc16(read_crc_state, read_pixel);
                if (checked_pixels == PIXELS - 1 &&
                    crc16(read_crc_state, read_pixel) != source_crc_state)
                    compare_error <= 1;
                if (read_column == FRAME_WIDTH - 1)
                    read_column <= 0;
                else
                    read_column <= read_column + 1'b1;
                checked_pixels <= checked_pixels + 1'b1;
                if (checked_pixels == PIXELS - 1)
                    compare_done <= 1;
            end
        end
    end
endmodule
