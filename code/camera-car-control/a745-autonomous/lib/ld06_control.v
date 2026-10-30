`timescale 1ns/1ps
`default_nettype none
// LD06 external speed mode: 30 kHz PWM, >=100 ms acquisition at 50%.
// A fresh command is required after lease expiry; heartbeat cannot restart it.
module ld06_control #(parameter CLK_HZ=50000000,ACQUIRE_MS=200,LEASE_MS=1000)(
    input wire clk,rst_n,ms_tick,enabled,update,renew,stop,
    input wire [9:0] duty_request,
    output wire pwm,output wire [31:0] status
);
    localparam PERIOD=CLK_HZ/30000<2 ? 2:CLK_HZ/30000;
    reg [15:0] phase,acquire_ms,age;
    reg [9:0] requested;
    reg expired,update_d,start;
    reg [31:0] numerator;
    reg [15:0] high_ticks;
    wire busy,done;wire [31:0] quotient;
    wire acquiring=acquire_ms<ACQUIRE_MS;
    wire [9:0] effective=acquiring ? 10'd500:expired ? 10'd0:requested;
    a741_divider divider(.clk(clk),.rst_n(rst_n),.cancel(!enabled || stop || expired),.start(start),
        .numerator(numerator),.denominator(16'd1000),.busy(busy),.done(done),.quotient(quotient));
    assign pwm=rst_n && enabled && !stop && (acquiring ? phase<PERIOD/2:!expired && phase<high_ticks);
    assign status={8'd0,(enabled && effective!=0),enabled,expired,acquiring,effective,requested};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin phase<=0;acquire_ms<=ACQUIRE_MS;age<=0;requested<=0;expired<=0;update_d<=0;start<=0;numerator<=0;high_ticks<=0;end
        else begin
            start<=0;update_d<=update && enabled && !stop;
            if(phase==PERIOD-1) phase<=0;else phase<=phase+1'b1;
            if(ms_tick) begin
                if(acquiring) acquire_ms<=acquire_ms+1'b1;
                if(age<LEASE_MS) age<=age+1'b1;
                if(age>=LEASE_MS-1 && requested!=0) begin requested<=0;high_ticks<=0;expired<=1;acquire_ms<=ACQUIRE_MS;end
            end
            if(renew && !expired) age<=0;
            if(done && !expired) high_ticks<=quotient[15:0];
            // Capture one cycle after the command register is updated upstream.
            if(update_d) begin
                requested<=duty_request;age<=0;expired<=0;
                numerator<=PERIOD*duty_request;start<=1;
                if(duty_request==0) begin high_ticks<=0;acquire_ms<=ACQUIRE_MS;end
                else if(requested==0 || expired) acquire_ms<=0;
            end
            if(stop || !enabled) begin requested<=0;high_ticks<=0;age<=0;expired<=0;update_d<=0;start<=0;acquire_ms<=ACQUIRE_MS;end
        end
endmodule
`default_nettype wire
