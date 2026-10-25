// OV5640 SCCB initialization controller using the 253-entry RGB ROM.
// The external interface is kept compatible with top_camera_led.
module ov5640_ctrl #(
    parameter integer CLK_HZ = 50_000_000,
    parameter integer SCCB_HZ = 100_000,
    parameter integer INIT_TIMEOUT = 50_000_000,
    parameter [7:0] SCCB_ADDR = 8'h78,
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 480,
    parameter IMAGE_FLIP_EN = 1'b0,
    parameter IMAGE_MIRROR_EN = 1'b0,
    parameter integer TABLE_LAST = 253,
    // Entry 1 is the sensor software reset.  The table specifies about 5 ms
    // before entry 2 (software power-down) is written.
    parameter integer RESET_DELAY_CYCLES = (CLK_HZ / 200)
) (
    input clk, input rst_n, input enable,
    inout sccb_sda, inout sccb_scl,
    output reg init_busy, output reg init_done, output reg init_error,
    output reg [7:0] last_read_id, output reg [7:0] table_index
);
    localparam [3:0] ST_IDLE=0, ST_LAUNCH=1, ST_ROM_WAIT1=2,
        ST_ROM_WAIT2=3, ST_XFER_WAIT=4, ST_DELAY=5,
        ST_READ_A_LAUNCH=6, ST_READ_A_WAIT=7,
        ST_READ_B_LAUNCH=8, ST_READ_B_WAIT=9, ST_HALTED=10;
    localparam integer DELAY_LIMIT = (RESET_DELAY_CYCLES < 1) ? 1 : RESET_DELAY_CYCLES;
    localparam integer DELAY_W = (DELAY_LIMIT < 2) ? 1 : $clog2(DELAY_LIMIT + 1);

    reg [3:0] state;
    reg [7:0] sensor_id_high;
    reg xfer_read;
    reg [15:0] xfer_reg;
    reg [7:0] xfer_data;
    reg [31:0] wait_count;
    reg [DELAY_W-1:0] delay_count;
    reg [7:0] rom_addr;
    wire [23:0] rom_q;
    wire [7:0] rd_data;
    wire xfer_busy, xfer_done, xfer_ack_error, xfer_timeout;

    // Launch one clock after request fields are registered; wait_count prevents
    // a completed transaction from being retriggered while xfer_done is high.
    wire launch = (state == ST_XFER_WAIT || state == ST_READ_A_WAIT ||
                   state == ST_READ_B_WAIT) && !xfer_busy && (wait_count == 0);

    ov5640_init_table_rgb #(
        .IMAGE_WIDTH(IMAGE_WIDTH), .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .IMAGE_FLIP_EN(IMAGE_FLIP_EN), .IMAGE_MIRROR_EN(IMAGE_MIRROR_EN)
    ) u_init_rom (
        .clk(clk), .addr(rom_addr), .q(rom_q)
    );

    sccb_master #(.CLK_HZ(CLK_HZ), .SCCB_HZ(SCCB_HZ), .TIMEOUT_CYCLES(INIT_TIMEOUT)) u_sccb (
        .clk(clk), .rst_n(rst_n), .start(launch), .read(xfer_read),
        .dev_addr(SCCB_ADDR), .reg_addr(xfer_reg), .wr_data(xfer_data), .rd_data(rd_data),
        .busy(xfer_busy), .done(xfer_done), .ack_error(xfer_ack_error), .timeout(xfer_timeout),
        .sccb_sda(sccb_sda), .sccb_scl(sccb_scl)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=ST_IDLE; init_busy<=0; init_done<=0; init_error<=0;
            last_read_id<=0; sensor_id_high<=0; table_index<=0;
            xfer_read<=0; xfer_reg<=0; xfer_data<=0; wait_count<=0;
            delay_count<=0; rom_addr<=0;
        end else if (!enable) begin
            state<=ST_IDLE; init_busy<=0; init_done<=0; init_error<=0;
            table_index<=0; wait_count<=0; delay_count<=0; rom_addr<=0;
        end else begin
            case (state)
                ST_IDLE: begin
                    init_busy<=1; init_done<=0; init_error<=0;
                    table_index<=0; rom_addr<=0; state<=ST_LAUNCH;
                end

                // The ROM is synchronous.  Two wait states ensure rom_q is
                // the word selected by rom_addr before it is copied to SCCB.
                ST_LAUNCH: begin
                    rom_addr<=table_index;
                    state<=ST_ROM_WAIT1;
                end
                ST_ROM_WAIT1: state<=ST_ROM_WAIT2;
                ST_ROM_WAIT2: begin
                    {xfer_reg,xfer_data} <= rom_q;
                    xfer_read<=0; wait_count<=0; state<=ST_XFER_WAIT;
                end

                ST_XFER_WAIT: begin
                    if (wait_count == 0) wait_count <= 1;
                    if (xfer_done) begin
                        if (xfer_ack_error || xfer_timeout) begin
                            init_error<=1; init_busy<=0; state<=ST_HALTED;
                        end else if (table_index == 8'd1) begin
                            // Official table comment: delay 5 ms after reset.
                            delay_count<=0; state<=ST_DELAY;
                        end else if (table_index + 1 >= TABLE_LAST) begin
                            state<=ST_READ_A_LAUNCH;
                        end else begin
                            table_index<=table_index+1'b1; state<=ST_LAUNCH;
                        end
                    end
                end

                ST_DELAY: begin
                    if (delay_count >= DELAY_LIMIT-1) begin
                        table_index<=8'd2; state<=ST_LAUNCH;
                    end else delay_count<=delay_count+1'b1;
                end

                ST_READ_A_LAUNCH: begin
                    xfer_read<=1; xfer_reg<=16'h300a; xfer_data<=0;
                    wait_count<=0; state<=ST_READ_A_WAIT;
                end
                ST_READ_A_WAIT: begin
                    if (wait_count == 0) wait_count <= 1;
                    if (xfer_done) begin
                        sensor_id_high<=rd_data; last_read_id<=rd_data;
                        if (xfer_ack_error || xfer_timeout || rd_data != 8'h56) begin
                            init_error<=1; init_done<=0; init_busy<=0; state<=ST_HALTED;
                        end else state<=ST_READ_B_LAUNCH;
                    end
                end
                ST_READ_B_LAUNCH: begin
                    xfer_read<=1; xfer_reg<=16'h300b; xfer_data<=0;
                    wait_count<=0; state<=ST_READ_B_WAIT;
                end
                ST_READ_B_WAIT: begin
                    if (wait_count == 0) wait_count <= 1;
                    if (xfer_done) begin
                        if (xfer_ack_error || xfer_timeout || rd_data != 8'h40) begin
                            init_error<=1; init_done<=0;
                        end else begin
                            init_done<=1; init_error<=0;
                        end
                        init_busy<=0; state<=ST_HALTED;
                    end
                end

                ST_HALTED: begin
                    // Terminal state: reset or disable/reenable starts over.
                    init_busy<=0;
                end
                default: state<=ST_HALTED;
            endcase
        end
    end
endmodule
