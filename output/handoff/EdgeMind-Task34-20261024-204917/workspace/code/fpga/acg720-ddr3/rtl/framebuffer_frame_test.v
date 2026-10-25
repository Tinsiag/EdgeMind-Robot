// One-frame test controller for the official chapter 38 FIFO/DDR path.
// The official read FIFO is FWFT=true, OUTPUT_REG=false: compare Q on pop.
module framebuffer_frame_test #(
    parameter FRAME_WIDTH = 800,
    parameter FRAME_HEIGHT = 480,
    parameter UI_TIMEOUT_CYCLES = 100000000
)(
    input reset_n,
    input wr_clk,
    input ui_clk,
    input rd_clk,
    input ui_reset,
    input calibrated,
    input source_valid,
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
    reg [26:0] timeout_count;
    reg [11:0] read_column;
    wire [7:0] expected_high = {read_column[6:0], 1'b1};
    wire [7:0] expected_low = {read_column[6:0], 1'b0} + 8'd2;
    wire [15:0] expected_pixel = {expected_high, expected_low};

    assign write_enable = wr_cal[1] && source_valid && !input_frame_done
                        && !write_fifo_full;
    assign read_enable = write_frame_done && (reads < BLOCKS)
                       && !ui_error && !timeout_error;
    assign read_pop = rd_cal[1] && rd_written[1] && !read_fifo_empty
                    && !compare_done;
    assign compare_pass = compare_done && !compare_error;

    always @(posedge wr_clk or negedge reset_n) begin
        if (!reset_n) begin
            wr_cal <= 0;
            input_pixels <= 0;
            input_frame_done <= 0;
            input_overflow <= 0;
        end else begin
            wr_cal <= {wr_cal[0], calibrated};
            if (!wr_cal[1]) begin
                input_pixels <= 0;
                input_frame_done <= 0;
                input_overflow <= 0;
            end else if (source_valid && !input_frame_done) begin
                if (write_fifo_full)
                    input_overflow <= 1;
                if (write_enable) begin
                    input_pixels <= input_pixels + 1'b1;
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
            done_ui <= 0;
        end else if (ui_reset || !calibrated) begin
            writes <= 0; reads <= 0; returns <= 0;
            write_frame_done <= 0; ui_error <= 0;
            timeout_count <= 0; timeout_error <= 0;
            done_ui <= 0;
        end else begin
            done_ui <= {done_ui[0], compare_done};
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
            read_column <= 0; checked_pixels <= 0;
            compare_done <= 0; compare_error <= 0;
            first_error_pixel <= 0;
            first_error_expected <= 0; first_error_actual <= 0;
        end else begin
            rd_cal <= {rd_cal[0], calibrated};
            rd_written <= {rd_written[0], write_frame_done};
            if (!rd_cal[1]) begin
                read_column <= 0; checked_pixels <= 0;
                compare_done <= 0; compare_error <= 0;
                first_error_pixel <= 0;
                first_error_expected <= 0; first_error_actual <= 0;
            end else if (read_pop) begin
                if (read_pixel != expected_pixel) begin
                    compare_error <= 1;
                    if (!compare_error) begin
                        first_error_pixel <= checked_pixels;
                        first_error_expected <= expected_pixel;
                        first_error_actual <= read_pixel;
                    end
                end
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
