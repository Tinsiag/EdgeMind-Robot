`timescale 1ns/1ps
// Passive checker for the Gowin native 128-bit / BL8 / 1:4 interface.
// Observe addresses 0, 8, ... 120, one at a time. Each sample is the last
// accepted write before the selected read command. No bus control outputs.
// Assumes in-order read responses, positive read latency, and fewer than
// 65536 outstanding reads. Those assumptions fit the native DDR interface.
module ddr_readback_monitor #(
    parameter integer TIMEOUT_BITS = 20
) (
    input wire clk,
    input wire rst_n,
    input wire ui_reset,
    input wire calibrated,
    input wire cmd_en,
    input wire cmd_ready,
    input wire [2:0] cmd,
    input wire [27:0] addr,
    input wire wr_en,
    input wire wr_ready,
    input wire [127:0] wr_data,
    input wire rd_valid,
    input wire [127:0] rd_data,
    output reg passed,
    output reg failed,
    output reg timed_out,
    output reg [4:0] checked_count
);
    localparam WAIT_WRITE = 2'd0, WAIT_READ = 2'd1,
               WAIT_DATA = 2'd2, DONE = 2'd3;
    reg [1:0] state;
    reg [3:0] target_index;
    reg [127:0] write_sample, expected_data;
    reg [15:0] issue_seq, return_seq, target_ticket;
    reg [TIMEOUT_BITS-1:0] wait_count;
    wire write_fire = cmd_en && cmd_ready && cmd == 3'd0 && wr_en && wr_ready;
    wire read_fire = cmd_en && cmd_ready && cmd == 3'd1;
    wire target_addr = addr == {21'd0, target_index, 3'b000};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= WAIT_WRITE;
            target_index <= 0;
            write_sample <= 0;
            expected_data <= 0;
            issue_seq <= 0;
            return_seq <= 0;
            target_ticket <= 0;
            wait_count <= 0;
            passed <= 0;
            failed <= 0;
            timed_out <= 0;
            checked_count <= 0;
        end else if (ui_reset || !calibrated) begin
            state <= WAIT_WRITE;
            target_index <= 0;
            write_sample <= 0;
            expected_data <= 0;
            issue_seq <= 0;
            return_seq <= 0;
            target_ticket <= 0;
            wait_count <= 0;
            passed <= 0;
            failed <= 0;
            timed_out <= 0;
            checked_count <= 0;
        end else begin
            if (read_fire) issue_seq <= issue_seq + 1'b1;
            if (rd_valid) return_seq <= return_seq + 1'b1;
            case (state)
                WAIT_WRITE: begin
                    if (write_fire && target_addr) begin
                        write_sample <= wr_data;
                        state <= WAIT_READ;
                    end
                end
                WAIT_READ: begin
                    // Track overwrites until the read command is accepted.
                    if (write_fire && target_addr) write_sample <= wr_data;
                    if (read_fire && target_addr) begin
                        expected_data <= write_sample;
                        target_ticket <= issue_seq;
                        wait_count <= 0;
                        state <= WAIT_DATA;
                    end
                end
                WAIT_DATA: begin
                    // Count every response, including unrelated prefetches.
                    // Later writes must not change this read's expected value.
                    if (rd_valid && return_seq == target_ticket) begin
                        if (rd_data != expected_data) begin
                            failed <= 1'b1;
                            state <= DONE;
                        end else begin
                            checked_count <= checked_count + 1'b1;
                            if (target_index == 4'd15) begin
                                passed <= 1'b1;
                                state <= DONE;
                            end else begin
                                target_index <= target_index + 1'b1;
                                state <= WAIT_WRITE;
                            end
                        end
                    end else if (&wait_count) begin
                        timed_out <= 1'b1;
                        failed <= 1'b1;
                        state <= DONE;
                    end else begin
                        wait_count <= wait_count + 1'b1;
                    end
                end
                DONE: state <= DONE;
                default: begin
                    failed <= 1'b1;
                    state <= DONE;
                end
            endcase
        end
    end
endmodule
