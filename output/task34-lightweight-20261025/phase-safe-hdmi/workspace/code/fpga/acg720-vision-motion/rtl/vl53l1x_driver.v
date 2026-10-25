`timescale 1ns/1ps
`default_nettype none
// Transaction engine is separate to allow a register-level sensor test model.
// Configuration derives from ST ULD, see vendor/ST-VL53L1X-LICENSE.txt.
module vl53l1x_driver #(parameter BOOT_TIMEOUT_MS=1000)(
    input wire clk,rst_n,ms_tick,
    output reg xshut_low,output reg xfer_start,xfer_read,
    output reg [15:0] xfer_reg,output reg [2:0] xfer_count,
    output reg [31:0] xfer_write,
    input wire xfer_busy,xfer_done,xfer_error,input wire [31:0] xfer_data,
    output reg init_done,error,sample_update,sample_valid,
    output reg [15:0] distance_mm,output reg [7:0] range_status
);
    localparam RESET=0,BOOT=1,ID=2,CONFIG=3,CAL_START=4,CAL_WAIT=5,CAL_CLEAR=6,
        CAL_STOP=7,VHV=8,VHV_INIT=9,TIME_A=10,TIME_B=11,OSC=12,PERIOD=13,
        RUN=14,POLL=15,STATUS=16,DISTANCE=17,CLEAR=18,FAILED=19;
    reg [4:0] phase;reg waiting;reg [15:0] elapsed,poll_ms;reg [6:0] index;
    reg [31:0] period_value;
    wire [7:0] config_value;
    vl53l1x_config_rom rom(.index(index),.value(config_value));
    always @* begin
        xfer_read=0;xfer_reg=0;xfer_count=1;xfer_write=0;
        case(phase)
            BOOT: begin xfer_read=1;xfer_reg=16'h00e5;end
            ID: begin xfer_read=1;xfer_reg=16'h010f;xfer_count=2;end
            CONFIG: begin xfer_reg=16'h002d+index;xfer_write={24'd0,config_value};end
            CAL_START,RUN: begin xfer_reg=16'h0087;xfer_write=32'h40;end
            CAL_WAIT,POLL: begin xfer_read=1;xfer_reg=16'h0031;end
            CAL_CLEAR,CLEAR: begin xfer_reg=16'h0086;xfer_write=1;end
            CAL_STOP: xfer_reg=16'h0087;
            VHV: begin xfer_reg=16'h0008;xfer_write=9;end
            VHV_INIT: xfer_reg=16'h000b;
            TIME_A: begin xfer_reg=16'h005e;xfer_count=2;xfer_write=32'h0060;end
            TIME_B: begin xfer_reg=16'h0061;xfer_count=2;xfer_write=32'h006e;end
            OSC: begin xfer_read=1;xfer_reg=16'h00de;xfer_count=2;end
            PERIOD: begin xfer_reg=16'h006c;xfer_count=4;xfer_write=period_value;end
            STATUS: begin xfer_read=1;xfer_reg=16'h0089;end
            DISTANCE: begin xfer_read=1;xfer_reg=16'h0096;xfer_count=2;end
            default: ;
        endcase
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            phase<=RESET;waiting<=0;elapsed<=0;poll_ms<=0;index<=0;period_value<=0;
            xshut_low<=1;xfer_start<=0;init_done<=0;error<=0;
            sample_update<=0;sample_valid<=0;distance_mm<=0;range_status<=255;
        end else begin
            xfer_start<=0;sample_update<=0;
            if(ms_tick) begin
                if(elapsed!=65535) elapsed<=elapsed+1'b1;
                if(poll_ms!=65535) poll_ms<=poll_ms+1'b1;
            end
            if(phase==RESET) begin
                if(elapsed>=2) begin xshut_low<=0;phase<=BOOT;elapsed<=0;poll_ms<=0;end
            end else if(phase!=FAILED) begin
                if(elapsed>=BOOT_TIMEOUT_MS) begin error<=1;sample_valid<=0;phase<=FAILED;end
                else if(!waiting && !xfer_busy && !xfer_start &&
                    ((phase!=BOOT && phase!=CAL_WAIT && phase!=POLL) || poll_ms>=2)) begin
                    xfer_start<=1;waiting<=1;poll_ms<=0;
                end else if(waiting && xfer_done) begin
                    waiting<=0;
                    if(xfer_error) begin error<=1;sample_valid<=0;phase<=FAILED;end
                    else case(phase)
                        BOOT: if(xfer_data[0]) begin phase<=ID;elapsed<=0;end
                        ID: if(xfer_data[15:0]==16'heacc) begin phase<=CONFIG;elapsed<=0;end
                            else begin error<=1;phase<=FAILED;end
                        CONFIG: begin
                            elapsed<=0;
                            if(index==90) phase<=CAL_START;else index<=index+1'b1;
                        end
                        CAL_START: begin phase<=CAL_WAIT;elapsed<=0;end
                        CAL_WAIT: if(xfer_data[0]) begin phase<=CAL_CLEAR;elapsed<=0;end
                        CAL_CLEAR: phase<=CAL_STOP;
                        CAL_STOP: phase<=VHV;
                        VHV: phase<=VHV_INIT;
                        VHV_INIT: phase<=TIME_A;
                        TIME_A: phase<=TIME_B;
                        TIME_B: phase<=OSC;
                        OSC: if(xfer_data[9:0]!=0) begin
                            // ST: oscillator calibration * 50 ms * 1.075.
                            period_value<=({22'd0,xfer_data[9:0]}*32'd215)>>2;phase<=PERIOD;
                        end else begin error<=1;phase<=FAILED;end
                        PERIOD: phase<=RUN;
                        RUN: begin phase<=POLL;init_done<=1;elapsed<=0;end
                        POLL: if(xfer_data[0]) begin phase<=STATUS;elapsed<=0;end
                        STATUS: begin range_status<=xfer_data[7:0]&8'h1f;phase<=DISTANCE;end
                        DISTANCE: begin distance_mm<=xfer_data[15:0];phase<=CLEAR;end
                        CLEAR: begin
                            sample_update<=1;sample_valid<=range_status==9 && distance_mm!=0;
                            phase<=POLL;elapsed<=0;
                        end
                        default: begin error<=1;phase<=FAILED;end
                    endcase
                end
            end
        end
endmodule
`default_nettype wire
