`timescale 1ns/1ps
`default_nettype none
// MPU6050 register interface. 100 Hz, +/-2 g, +/-2000 dps, DLPF=3.
// Poll INT_STATUS rather than relying on interrupt wiring/edge capture.
module mpu6050_driver #(parameter ALLOW_MPU6500=0)(
    input wire clk,rst_n,ms_tick,input wire [31:0] now_ms,
    output reg start,read,output reg [6:0] address,output reg [7:0] reg_addr,
    output reg [3:0] byte_count,output reg [111:0] write_data,
    input wire busy,done,error,input wire [111:0] read_data,
    output reg sample_update,valid,ready,
    output reg signed [15:0] ax,ay,az,gx,gy,gz,temperature,
    output reg [31:0] sample_time,sequence_id,errors,
    output reg [7:0] fault,who_am_i
);
    localparam WAIT_POWER=0,ISSUE=1,WAIT_RESULT=2,WAIT_RESET=3,POLL_WAIT=4,RETRY=5;
    reg [2:0] state;
    reg [4:0] operation;
    reg [15:0] delay_ms,age;
    reg tried_high;
    function [7:0] config_reg;
        input [4:0] index;
        begin case(index)
            0:config_reg=8'h6b;1:config_reg=8'h6c;2:config_reg=8'h1a;3:config_reg=8'h19;
            4:config_reg=8'h1b;5:config_reg=8'h1c;6:config_reg=8'h6a;7:config_reg=8'h38;
            default:config_reg=0;
        endcase end
    endfunction
    function [7:0] config_value;
        input [4:0] index;
        begin case(index)
            0:config_value=1;2:config_value=3;3:config_value=9;4:config_value=8'h18;7:config_value=1;
            default:config_value=0;
        endcase end
    endfunction
    // Operation 0=WHO, 1=reset, 2..9=configuration, 10=status, 11=burst.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=WAIT_POWER;operation<=0;delay_ms<=0;age<=65535;tried_high<=0;
            start<=0;read<=1;address<=7'h68;reg_addr<=8'h75;byte_count<=1;write_data<=0;
            sample_update<=0;valid<=0;ready<=0;ax<=0;ay<=0;az<=0;gx<=0;gy<=0;gz<=0;temperature<=0;
            sample_time<=0;sequence_id<=0;errors<=0;fault<=0;who_am_i<=0;
        end else begin
            start<=0;sample_update<=0;
            if(ms_tick) begin
                if(delay_ms!=65535) delay_ms<=delay_ms+1'b1;
                if(age!=65535) age<=age+1'b1;
                if(age>=149) valid<=0;
            end
            case(state)
                WAIT_POWER: if(delay_ms>=100) begin state<=ISSUE;delay_ms<=0;end
                ISSUE: if(!busy) begin
                    read<=0;byte_count<=1;write_data<=0;start<=1;state<=WAIT_RESULT;delay_ms<=0;
                    case(operation)
                        0:begin read<=1;reg_addr<=8'h75;end
                        1:begin reg_addr<=8'h6b;write_data<=8'h80;end
                        2:begin reg_addr<=8'h6b;write_data<=8'h01;end
                        3:begin reg_addr<=8'h6c;write_data<=0;end
                        4:begin reg_addr<=8'h1a;write_data<=3;end
                        5:begin reg_addr<=8'h19;write_data<=9;end
                        6:begin reg_addr<=8'h1b;write_data<=8'h18;end
                        7:begin reg_addr<=8'h1c;write_data<=0;end
                        8:begin reg_addr<=8'h6a;write_data<=0;end
                        9:begin reg_addr<=8'h38;write_data<=1;end
                        10:begin read<=1;reg_addr<=8'h3a;end
                        11:begin read<=1;reg_addr<=8'h3b;byte_count<=14;end
                        20:begin reg_addr<=8'h1d;write_data<=3;end
                        21:begin read<=1;reg_addr<=8'h1d;end
                        default:if(operation>=12 && operation<=19) begin read<=1;reg_addr<=config_reg(operation-12);end
                            else begin start<=0;state<=RETRY;end
                    endcase
                end
                WAIT_RESULT: if(done || delay_ms>=30) begin
                    if(error || delay_ms>=30) begin
                        valid<=0;ready<=0;errors<=errors+1'b1;fault<=1;delay_ms<=0;
                        if(operation==0 && !tried_high) begin address<=7'h69;tried_high<=1;state<=ISSUE;end
                        else state<=RETRY;
                    end else case(operation)
                        0:begin who_am_i<=read_data[7:0];
                        if(read_data[7:0]!=8'h68 && !(ALLOW_MPU6500!=0 && read_data[7:0]==8'h70)) begin
                            valid<=0;ready<=0;errors<=errors+1'b1;fault<=2;delay_ms<=0;
                            // An incompatible responder at 0x68 must not hide a supported device at 0x69.
                            if(!tried_high) begin address<=7'h69;tried_high<=1;state<=ISSUE;end
                            else state<=RETRY;
                        end else begin operation<=1;state<=ISSUE;end end
                        1:begin state<=WAIT_RESET;delay_ms<=0;end
                        9:begin operation<=12;state<=ISSUE;end
                        10:begin
                            delay_ms<=0;
                            if(read_data[0]) begin operation<=11;state<=ISSUE;end
                            else if(age>=150) begin
                                ready<=0;valid<=0;errors<=errors+1'b1;fault<=3;state<=RETRY;
                            end else state<=POLL_WAIT;
                        end
                        11:begin
                            ax<=read_data[111:96];ay<=read_data[95:80];az<=read_data[79:64];
                            temperature<=read_data[63:48];gx<=read_data[47:32];gy<=read_data[31:16];gz<=read_data[15:0];
                            sample_update<=1;valid<=1;age<=0;sample_time<=now_ms;sequence_id<=sequence_id+1'b1;
                            operation<=10;delay_ms<=0;state<=POLL_WAIT;
                        end
                        20:begin operation<=21;state<=ISSUE;end
                        21:begin
                            if(read_data[7:0]!=3) begin
                                ready<=0;valid<=0;errors<=errors+1'b1;fault<=4;state<=RETRY;delay_ms<=0;
                            end else begin ready<=1;fault<=0;operation<=10;delay_ms<=0;age<=0;state<=POLL_WAIT;end
                        end
                        default:if(operation>=12) begin
                            if(read_data[7:0]!=config_value(operation-12)) begin
                                ready<=0;valid<=0;errors<=errors+1'b1;fault<=4;state<=RETRY;delay_ms<=0;
                            end else if(operation==19) begin
                                if(who_am_i==8'h70) begin operation<=20;state<=ISSUE;end
                                else begin ready<=1;fault<=0;operation<=10;delay_ms<=0;age<=0;state<=POLL_WAIT;end
                            end else begin operation<=operation+1'b1;state<=ISSUE;end
                        end else begin operation<=operation+1'b1;state<=ISSUE;end
                    endcase
                end
                WAIT_RESET:if(delay_ms>=100) begin operation<=2;state<=ISSUE;end
                POLL_WAIT:if(delay_ms>=2) state<=ISSUE;
                RETRY:if(delay_ms>=1000) begin operation<=0;address<=7'h68;tried_high<=0;state<=ISSUE;end
                default:state<=RETRY;
            endcase
        end
endmodule
`default_nettype wire
