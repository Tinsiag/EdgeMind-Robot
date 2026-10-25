// One open-drain SCCB transaction: 8-bit device address, 16-bit register, 8-bit data.
// start is sampled every clk while idle; keep transaction inputs stable until start.
// done pulses for one clk. Error flags persist until the next accepted start.
module sccb_master #(
    parameter integer CLK_HZ = 50_000_000,
    parameter integer SCCB_HZ = 100_000,
    parameter integer TIMEOUT_CYCLES = 1_000_000
) (
    input clk, input rst_n, input start, input read,
    input [7:0] dev_addr, input [15:0] reg_addr, input [7:0] wr_data,
    output reg [7:0] rd_data, output reg busy, output reg done,
    output reg ack_error, output reg timeout,
    inout sccb_sda, inout sccb_scl
);
    localparam integer QUARTER_DIV = (CLK_HZ / (4*SCCB_HZ) < 1) ?
                                    1 : CLK_HZ / (4*SCCB_HZ);
    localparam integer DW = (QUARTER_DIV < 2) ? 1 : $clog2(QUARTER_DIV);
    // Clamp zero/one-cycle configurations so TIMEOUT_CYCLES-1 cannot
    // underflow and create an effectively unbounded watchdog.
    localparam integer TIMEOUT_LIMIT = (TIMEOUT_CYCLES < 1) ? 1 : TIMEOUT_CYCLES;
    localparam integer TW = (TIMEOUT_LIMIT < 2) ? 1 : $clog2(TIMEOUT_LIMIT+1);
    localparam [4:0] IDLE=0, BUS_IDLE=1, START_HOLD=2,
        TX_LOW=3, TX_RAISE=4, TX_HIGH=5, TX_FALL=6,
        ACK_LOW=7, ACK_RAISE=8, ACK_HIGH=9, ACK_FALL=10,
        REP_LOW=11, REP_RAISE=12, REP_HIGH=13,
        RX_LOW=14, RX_RAISE=15, RX_HIGH=16, RX_FALL=17,
        NACK_LOW=18, NACK_RAISE=19, NACK_HIGH=20, NACK_FALL=21,
        STOP_LOW=22, STOP_RAISE=23, STOP_HIGH=24, STOP_RELEASE=25, FINISH=26;
    reg [4:0] state;
    reg [DW-1:0] divider;
    reg [TW-1:0] watchdog;
    reg sda_low, scl_low;
    reg [1:0] sda_sync, scl_sync;
    reg [7:0] addr_latched, data_latched, tx_byte;
    reg [15:0] reg_latched;
    reg read_latched;
    reg [2:0] bit_index, byte_index;
    wire tick = (divider == QUARTER_DIV-1);
    wire sda_in = sda_sync[1];
    wire scl_in = scl_sync[1];
    assign sccb_sda = sda_low ? 1'b0 : 1'bz;
    assign sccb_scl = scl_low ? 1'b0 : 1'bz;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin sda_sync<=2'b11; scl_sync<=2'b11; end
        else begin
            sda_sync <= {sda_sync[0], sccb_sda};
            scl_sync <= {scl_sync[0], sccb_scl};
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; divider<=0; watchdog<=0;
            sda_low<=0; scl_low<=0; addr_latched<=0; data_latched<=0;
            reg_latched<=0; read_latched<=0; tx_byte<=0;
            bit_index<=7; byte_index<=0; rd_data<=0;
            busy<=0; done<=0; ack_error<=0; timeout<=0;
        end else begin
            done <= 1'b0;
            if (!busy) begin
                divider<=0; watchdog<=0;
                if (start) begin
                    addr_latched<=dev_addr & 8'hfe;
                    data_latched<=wr_data; reg_latched<=reg_addr; read_latched<=read;
                    tx_byte<=dev_addr & 8'hfe; bit_index<=7; byte_index<=0;
                    rd_data<=0; ack_error<=0; timeout<=0; busy<=1;
                    sda_low<=0; scl_low<=0; state<=BUS_IDLE;
                end
            end else if (watchdog >= TIMEOUT_LIMIT-1) begin
                // A stuck line cannot be forced high; release both and report failure.
                // This is a bounded abort, not an automatic 9-clock bus-recovery routine.
                sda_low<=0; scl_low<=0; timeout<=1; busy<=0; done<=1; state<=IDLE;
            end else begin
                watchdog<=watchdog+1'b1;
                if (tick) begin
                    divider<=0;
                    case (state)
                        BUS_IDLE: if (scl_in && sda_in) begin
                            sda_low<=1; state<=START_HOLD;
                        end
                        START_HOLD: begin scl_low<=1; state<=TX_LOW; end
                        TX_LOW: begin sda_low<=!tx_byte[bit_index]; state<=TX_RAISE; end
                        TX_RAISE: begin scl_low<=0; state<=TX_HIGH; end
                        TX_HIGH: if (scl_in) state<=TX_FALL;
                        TX_FALL: begin
                            scl_low<=1;
                            if (bit_index==0) state<=ACK_LOW;
                            else begin bit_index<=bit_index-1'b1; state<=TX_LOW; end
                        end
                        ACK_LOW: begin sda_low<=0; state<=ACK_RAISE; end
                        ACK_RAISE: begin scl_low<=0; state<=ACK_HIGH; end
                        ACK_HIGH: if (scl_in) begin
                            if (sda_in) ack_error<=1;
                            state<=ACK_FALL;
                        end
                        ACK_FALL: begin
                            scl_low<=1; bit_index<=7;
                            // ACK_HIGH samples the current ACK bit with a
                            // nonblocking assignment, so test SDA here as
                            // well as the sticky flag to stop immediately on
                            // this byte's NACK.
                            if (ack_error || sda_in) state<=STOP_LOW;
                            else case (byte_index)
                                0: begin tx_byte<=reg_latched[15:8]; byte_index<=1; state<=TX_LOW; end
                                1: begin tx_byte<=reg_latched[7:0]; byte_index<=2; state<=TX_LOW; end
                                2: if (read_latched) begin
                                    tx_byte<=addr_latched|8'h01; byte_index<=4; state<=REP_LOW;
                                end else begin
                                    tx_byte<=data_latched; byte_index<=3; state<=TX_LOW;
                                end
                                3: state<=STOP_LOW;
                                4: state<=RX_LOW;
                                default: state<=STOP_LOW;
                            endcase
                        end
                        REP_LOW: begin sda_low<=0; state<=REP_RAISE; end
                        REP_RAISE: begin scl_low<=0; state<=REP_HIGH; end
                        REP_HIGH: if (scl_in) begin sda_low<=1; state<=START_HOLD; end
                        RX_LOW: begin sda_low<=0; state<=RX_RAISE; end
                        RX_RAISE: begin scl_low<=0; state<=RX_HIGH; end
                        RX_HIGH: if (scl_in) begin
                            rd_data[bit_index]<=sda_in; state<=RX_FALL;
                        end
                        RX_FALL: begin
                            scl_low<=1;
                            if (bit_index==0) state<=NACK_LOW;
                            else begin bit_index<=bit_index-1'b1; state<=RX_LOW; end
                        end
                        // Single-byte reads are terminated by master NACK (released SDA).
                        NACK_LOW: begin sda_low<=0; state<=NACK_RAISE; end
                        NACK_RAISE: begin scl_low<=0; state<=NACK_HIGH; end
                        NACK_HIGH: if (scl_in) state<=NACK_FALL;
                        NACK_FALL: begin scl_low<=1; state<=STOP_LOW; end
                        STOP_LOW: begin sda_low<=1; state<=STOP_RAISE; end
                        STOP_RAISE: begin scl_low<=0; state<=STOP_HIGH; end
                        STOP_HIGH: if (scl_in) begin sda_low<=0; state<=STOP_RELEASE; end
                        STOP_RELEASE: state<=FINISH;
                        FINISH: begin busy<=0; done<=1; state<=IDLE; end
                        default: begin busy<=0; done<=1; timeout<=1; sda_low<=0; scl_low<=0; state<=IDLE; end
                    endcase
                end else divider<=divider+1'b1;
            end
        end
    end
endmodule
