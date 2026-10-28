`timescale 1ns/1ps
`default_nettype none
module ov5640_board_init #(
    parameter CLK_HZ=50000000,WIDTH=800,HEIGHT=480,
    parameter integer MAX_ATTEMPTS=3,
    parameter integer RETRY_DELAY_MS=50
)(
    input wire clk,rst_n,
    output wire camera_reset_n,
    inout wire scl,sda,
    output reg ready,error
);
    // OV5640 power-up: RESETB low for at least 1 ms, then wait 21 ms before
    // the first SCCB transaction.  A transient NACK/readback failure must not
    // leave the camera permanently disabled after an FPGA reload, so restart
    // the complete table and verification a bounded number of times.
    localparam integer RESET_CYCLES = (CLK_HZ/1000 < 1) ? 1 : CLK_HZ/1000;
    localparam integer START_CYCLES = (CLK_HZ/1000*21 < 1) ? 1 : CLK_HZ/1000*21;
    localparam integer RETRY_CYCLES = (CLK_HZ/1000*RETRY_DELAY_MS < 1) ? 1 : CLK_HZ/1000*RETRY_DELAY_MS;
    localparam integer BOOT_W = (START_CYCLES<2) ? 1 : $clog2(START_CYCLES+1);
    localparam integer RETRY_W = (RETRY_CYCLES<2) ? 1 : $clog2(RETRY_CYCLES+1);
    localparam integer ATTEMPT_W = (MAX_ATTEMPTS<2) ? 1 : $clog2(MAX_ATTEMPTS+1);
    reg [BOOT_W-1:0] boot_count;
    reg [RETRY_W-1:0] retry_count;
    reg init_enable;
    reg [ATTEMPT_W-1:0] attempt_count;
    wire sensor_released=boot_count>=RESET_CYCLES;
    wire enable=init_enable;
    assign camera_reset_n=rst_n && sensor_released;
    wire init_done,init_error;
    ov5640_ctrl #(.CLK_HZ(CLK_HZ),.SCCB_HZ(100000),.IMAGE_WIDTH(WIDTH),
        .IMAGE_HEIGHT(HEIGHT),.TABLE_LAST(254)) init(
        .clk(clk),.rst_n(rst_n),.enable(enable),.sccb_sda(sda),.sccb_scl(scl),
        .init_busy(),.init_done(init_done),.init_error(init_error),.last_read_id(),.table_index());
    localparam [2:0] ST_WAIT_START=0,ST_RUN_INIT=1,ST_VERIFY=2,
        ST_RETRY_WAIT=3,ST_DONE=4,ST_ERROR=5;
    reg [2:0] state;
    reg [3:0] index;
    reg start;
    wire done,ack_error,timeout;
    wire [7:0] value;
    reg [15:0] address;
    reg [7:0] expected;
    always @* begin
        address=16'h3808;expected=WIDTH>>8;
        case(index)
            1:begin address=16'h3809;expected=WIDTH & 255;end
            2:begin address=16'h380a;expected=HEIGHT>>8;end
            3:begin address=16'h380b;expected=HEIGHT & 255;end
            4:begin address=16'h4300;expected=8'h61;end
            5:begin address=16'h501f;expected=8'h01;end
            6:begin address=16'h5001;expected=8'ha3;end
            7:begin address=16'h503d;expected=8'h00;end
            8:begin address=16'h4741;expected=8'h00;end
            default:begin end
        endcase
    end
    sccb_master #(.CLK_HZ(CLK_HZ),.SCCB_HZ(100000)) verify(
        .clk(clk),.rst_n(rst_n),.start(start),.read(1'b1),.dev_addr(8'h78),
        .reg_addr(address),.wr_data(8'd0),.rd_data(value),.busy(),.done(done),
        .ack_error(ack_error),.timeout(timeout),.sccb_sda(sda),.sccb_scl(scl));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            boot_count<=0;retry_count<=0;init_enable<=0;attempt_count<=0;
            state<=ST_WAIT_START;index<=0;start<=0;ready<=0;error<=0;
        end else begin
            start<=0;
            if(boot_count<START_CYCLES) boot_count<=boot_count+1'b1;
            case(state)
                ST_WAIT_START: begin
                    if(boot_count>=START_CYCLES-1) begin
                        init_enable<=1;attempt_count<=1;state<=ST_RUN_INIT;
                    end
                end
                ST_RUN_INIT: begin
                    if(init_error) begin
                        init_enable<=0;ready<=0;
                        if(attempt_count<MAX_ATTEMPTS) begin
                            retry_count<=0;attempt_count<=attempt_count+1'b1;
                            state<=ST_RETRY_WAIT;
                        end else begin error<=1;state<=ST_ERROR;end
                    end else if(init_done) begin
                        start<=1;state<=ST_VERIFY;
                    end
                end
                ST_VERIFY: begin
                    if(done) begin
                        if(ack_error || timeout || value!=expected) begin
                            init_enable<=0;ready<=0;
                            if(attempt_count<MAX_ATTEMPTS) begin
                                retry_count<=0;attempt_count<=attempt_count+1'b1;
                                state<=ST_RETRY_WAIT;
                            end else begin error<=1;state<=ST_ERROR;end
                        end else if(index==8) begin
                            ready<=1;state<=ST_DONE;
                        end else begin
                            index<=index+1'b1;state<=ST_VERIFY;start<=1;
                        end
                    end
                end
                ST_RETRY_WAIT: begin
                    if(retry_count>=RETRY_CYCLES-1) begin
                        retry_count<=0;index<=0;init_enable<=1;state<=ST_RUN_INIT;
                    end else retry_count<=retry_count+1'b1;
                end
                ST_DONE: begin end
                ST_ERROR: begin end
                default: state<=ST_ERROR;
            endcase
        end
endmodule
`default_nettype wire
