`timescale 1ns/1ps
`default_nettype none
// WIT standard 55/type/8 payload/checksum frames. Values retain raw Q15 units.
module jy901_parser #(parameter STALE_MS=150)(
    input wire clk,rst_n,ms_tick,byte_valid,framing_error,
    input wire [7:0] data,
    output reg angle_update,gyro_update,angle_valid,gyro_valid,
    output reg signed [15:0] roll,pitch,yaw,gx,gy,gz,
    output reg [31:0] angle_time,gyro_time,angle_seq,gyro_seq,errors,
    output reg [31:0] now_ms
);
    reg [87:0] window;
    reg [3:0] filled;
    reg [15:0] angle_age,gyro_age;
    reg [7:0] sum;
    reg [87:0] candidate;
    integer i;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            window<=0;filled<=0;angle_update<=0;gyro_update<=0;
            angle_valid<=0;gyro_valid<=0;roll<=0;pitch<=0;yaw<=0;gx<=0;gy<=0;gz<=0;
            angle_time<=0;gyro_time<=0;angle_seq<=0;gyro_seq<=0;errors<=0;now_ms<=0;
            angle_age<=65535;gyro_age<=65535;
        end else begin
            angle_update<=0;gyro_update<=0;
            if(ms_tick) begin
                now_ms<=now_ms+1'b1;
                if(angle_age!=65535) angle_age<=angle_age+1'b1;
                if(gyro_age!=65535) gyro_age<=gyro_age+1'b1;
                if(angle_age>=STALE_MS-1) angle_valid<=0;
                if(gyro_age>=STALE_MS-1) gyro_valid<=0;
            end
            if(framing_error) begin filled<=0;errors<=errors+1'b1;end
            else if(byte_valid) begin
                candidate={data,window[87:8]};window<=candidate;
                if(filled<11) filled<=filled+1'b1;
                if(filled>=10 && candidate[7:0]==8'h55 &&
                    (candidate[15:8]==8'h52 || candidate[15:8]==8'h53)) begin
                    sum=0;for(i=0;i<10;i=i+1) sum=sum+candidate[i*8+:8];
                    if(sum!=data) errors<=errors+1'b1;
                    else if(candidate[15:8]==8'h53) begin
                        roll<=candidate[31:16];pitch<=candidate[47:32];yaw<=candidate[63:48];
                        angle_update<=1;angle_valid<=1;angle_age<=0;angle_time<=now_ms;angle_seq<=angle_seq+1'b1;
                    end else begin
                        gx<=candidate[31:16];gy<=candidate[47:32];gz<=candidate[63:48];
                        gyro_update<=1;gyro_valid<=1;gyro_age<=0;gyro_time<=now_ms;gyro_seq<=gyro_seq+1'b1;
                    end
                end
            end
        end
endmodule
`default_nettype wire
