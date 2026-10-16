`timescale 1ns/1ps
`default_nettype none
// A719 -- VM MUST BE PHYSICALLY DISCONNECTED. Static logic-level measurement only.
// S1 held: left IN1 high. S2 held: left IN2 high. Release/both/S0: low.
// No PWM, motor timer, UART or motor-driving authorization. Right INs always low.
module acg720_gpio_static #(
    parameter integer CLK_HZ=50000000,
    parameter integer STARTUP_MS=100,
    parameter integer DEBOUNCE_MS=20
)(
    input wire clk,stop_n,left_key_n,right_key_n,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,camera_reset_n,
    output wire [7:0] led
);
    localparam integer MS_CYCLES=CLK_HZ/1000;
    reg [31:0] startup=0;
    reg startup_done=0;
    reg [1:0] release_sync=0;
    always @(posedge clk or negedge stop_n) begin
        if(!stop_n) begin startup<=0;startup_done<=0;release_sync<=0;end
        else begin
            if(!startup_done) begin
                if(startup==(MS_CYCLES*STARTUP_MS)-1) startup_done<=1;
                else startup<=startup+1'b1;
            end
            release_sync<={release_sync[0],startup_done};
        end
    end
    wire ready=stop_n && release_sync[1];
    (* syn_preserve=1 *) reg [1:0] key_meta=0,key_sync=0;
    (* syn_preserve=1 *) reg [3:0] enc_meta=0,enc_sync=0;
    reg [31:0] ms_count=0;
    wire ms_tick=ms_count==MS_CYCLES-1;
    reg [1:0] debounced=0,candidate=0;
    reg [31:0] debounce_count=0,release_count=0;
    reg armed=0;
    reg [31:0] hb_count=0;
    reg heartbeat=0;
    always @(posedge clk or negedge ready) begin
        if(!ready) begin
            key_meta<=0;key_sync<=0;enc_meta<=0;enc_sync<=0;
            ms_count<=0;debounced<=0;candidate<=0;debounce_count<=0;release_count<=0;armed<=0;
            hb_count<=0;heartbeat<=0;
        end else begin
            key_meta<={~right_key_n,~left_key_n};key_sync<=key_meta;
            enc_meta<={right_enc_b,right_enc_a,left_enc_b,left_enc_a};enc_sync<=enc_meta;
            if(ms_tick) begin
                ms_count<=0;
                if(key_sync!=candidate) begin candidate<=key_sync;debounce_count<=0;end
                else if(key_sync==debounced) debounce_count<=0;
                else if(debounce_count==DEBOUNCE_MS-1) begin debounced<=key_sync;debounce_count<=0;end
                else debounce_count<=debounce_count+1'b1;
                if(!armed) begin
                    if(key_sync==0 && debounced==0 && left_key_n && right_key_n) begin
                        if(release_count==DEBOUNCE_MS-1) begin armed<=1;release_count<=0;end
                        else release_count<=release_count+1'b1;
                    end else release_count<=0;
                end
            end else ms_count<=ms_count+1'b1;
            // A chord disarms until both keys have been released again.
            if((!left_key_n && !right_key_n) || key_sync==2'b11) begin armed<=0;release_count<=0;end
            if(hb_count==CLK_HZ/2-1) begin hb_count<=0;heartbeat<=~heartbeat;end
            else hb_count<=hb_count+1'b1;
        end
    end
    // Raw keys additionally gate physical outputs: release/S0/both kill immediately.
    assign left_in1=ready && armed && !left_key_n && right_key_n && key_sync==2'b01 && debounced==2'b01;
    assign left_in2=ready && armed && left_key_n && !right_key_n && key_sync==2'b10 && debounced==2'b10;
    assign right_in1=1'b0;
    assign right_in2=1'b0;
    assign camera_reset_n=1'b0;
    assign led={heartbeat,enc_sync,left_in2,left_in1,ready};
endmodule
`default_nettype wire
