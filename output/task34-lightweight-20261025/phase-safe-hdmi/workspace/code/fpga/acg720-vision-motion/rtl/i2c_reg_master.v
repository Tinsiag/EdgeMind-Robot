`timescale 1ns/1ps
`default_nettype none
// 7-bit device address, 16-bit register index, big-endian 1..4-byte transfers.
// SDA/SCL only ever drive low; ACK, repeated START and stretching are checked.
module i2c_reg_master #(parameter CLK_HZ=50000000,I2C_HZ=100000,TIMEOUT_CYCLES=1000000)(
    input wire clk,rst_n,start,read,
    input wire [6:0] address,input wire [15:0] reg_addr,
    input wire [2:0] byte_count,input wire [31:0] write_data,
    output reg [31:0] read_data,output reg busy,done,error,
    inout wire sda,scl
);
    localparam DIV=(CLK_HZ/(I2C_HZ*4)<1)?1:CLK_HZ/(I2C_HZ*4);
    localparam IDLE=0,BUS=1,START=2,TX0=3,TX1=4,TX2=5,TX3=6,
        ACK0=7,ACK1=8,ACK2=9,ACK3=10,REP0=11,REP1=12,REP2=13,
        RX0=14,RX1=15,RX2=16,RX3=17,MACK0=18,MACK1=19,MACK2=20,MACK3=21,
        STOP0=22,STOP1=23,STOP2=24,STOP3=25;
    reg [4:0] state;reg [31:0] divider,watchdog,wr_q;
    reg sda_low,scl_low,read_q;reg [6:0] address_q;
    reg [15:0] reg_q;reg [7:0] tx_byte;
    reg [2:0] bit_index,nbytes,data_index,header;
    (* ASYNC_REG="TRUE" *) reg [1:0] sda_sync,scl_sync;
    wire tick=divider==DIV-1;
    function [7:0] write_byte;
        input [31:0] word_data;input [2:0] position;
        reg [31:0] shifted_data;
        begin shifted_data=word_data >> (position*8);write_byte=shifted_data[7:0];end
    endfunction
    assign sda=sda_low?1'b0:1'bz;assign scl=scl_low?1'b0:1'bz;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin sda_sync<=3;scl_sync<=3;end
        else begin sda_sync<={sda_sync[0],sda};scl_sync<={scl_sync[0],scl};end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=IDLE;divider<=0;watchdog<=0;wr_q<=0;sda_low<=0;scl_low<=0;
            read_q<=0;address_q<=0;reg_q<=0;tx_byte<=0;bit_index<=7;
            nbytes<=1;data_index<=0;header<=0;read_data<=0;busy<=0;done<=0;error<=0;
        end else begin
            done<=0;
            if(!busy) begin
                divider<=0;watchdog<=0;
                if(start) begin
                    if(byte_count<1 || byte_count>4) begin done<=1;error<=1;end
                    else begin
                        address_q<=address;reg_q<=reg_addr;read_q<=read;wr_q<=write_data;
                        nbytes<=byte_count;data_index<=0;header<=0;bit_index<=7;
                        tx_byte<={address,1'b0};read_data<=0;error<=0;busy<=1;
                        sda_low<=0;scl_low<=0;state<=BUS;
                    end
                end
            end else if(watchdog>=TIMEOUT_CYCLES-1) begin
                sda_low<=0;scl_low<=0;error<=1;busy<=0;done<=1;state<=IDLE;
            end else begin
                watchdog<=watchdog+1'b1;
                if(tick) begin
                    divider<=0;
                    case(state)
                        BUS: if(sda_sync[1] && scl_sync[1]) begin sda_low<=1;state<=START;end
                        START: begin scl_low<=1;state<=TX0;end
                        TX0: begin sda_low<=!tx_byte[bit_index];state<=TX1;end
                        TX1: begin scl_low<=0;state<=TX2;end
                        TX2: if(scl_sync[1]) state<=TX3;
                        TX3: begin scl_low<=1;if(bit_index==0) state<=ACK0;else begin bit_index<=bit_index-1'b1;state<=TX0;end end
                        ACK0: begin sda_low<=0;state<=ACK1;end
                        ACK1: begin scl_low<=0;state<=ACK2;end
                        ACK2: if(scl_sync[1]) begin if(sda_sync[1]) error<=1;state<=ACK3;end
                        ACK3: begin
                            scl_low<=1;bit_index<=7;
                            if(error) state<=STOP0;
                            else case(header)
                                0: begin tx_byte<=reg_q[15:8];header<=1;state<=TX0;end
                                1: begin tx_byte<=reg_q[7:0];header<=2;state<=TX0;end
                                2: if(read_q) begin tx_byte<={address_q,1'b1};header<=3;state<=REP0;end
                                   else begin tx_byte<=write_byte(wr_q,nbytes-3'd1);header<=4;state<=TX0;end
                                3: state<=RX0;
                                4: if(data_index+1>=nbytes) state<=STOP0;
                                   else begin data_index<=data_index+1'b1;tx_byte<=write_byte(wr_q,nbytes-3'd2-data_index);state<=TX0;end
                                default: begin error<=1;state<=STOP0;end
                            endcase
                        end
                        REP0: begin sda_low<=0;state<=REP1;end
                        REP1: begin scl_low<=0;state<=REP2;end
                        REP2: if(scl_sync[1]) begin sda_low<=1;state<=START;end
                        RX0: begin sda_low<=0;state<=RX1;end
                        RX1: begin scl_low<=0;state<=RX2;end
                        RX2: if(scl_sync[1]) begin read_data<={read_data[30:0],sda_sync[1]};state<=RX3;end
                        RX3: begin scl_low<=1;if(bit_index==0) state<=MACK0;else begin bit_index<=bit_index-1'b1;state<=RX0;end end
                        MACK0: begin sda_low<=data_index+1<nbytes;state<=MACK1;end
                        MACK1: begin scl_low<=0;state<=MACK2;end
                        MACK2: if(scl_sync[1]) state<=MACK3;
                        MACK3: begin
                            scl_low<=1;bit_index<=7;
                            if(data_index+1>=nbytes) state<=STOP0;
                            else begin data_index<=data_index+1'b1;state<=RX0;end
                        end
                        STOP0: begin sda_low<=1;scl_low<=1;state<=STOP1;end
                        STOP1: begin scl_low<=0;state<=STOP2;end
                        STOP2: if(scl_sync[1]) begin sda_low<=0;state<=STOP3;end
                        STOP3: begin busy<=0;done<=1;state<=IDLE;end
                        default: begin error<=1;state<=STOP0;end
                    endcase
                end else divider<=divider+1'b1;
            end
        end
endmodule
`default_nettype wire
