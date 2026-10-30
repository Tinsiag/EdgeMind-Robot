`timescale 1ns/1ps
`default_nettype none
// ACG720 S1 is active-low (A20).  Synchronize and debounce it, then emit
// one clock-wide pulse on each stable press.
module a741_button_debounce #(parameter CLK_HZ=50000000,DEBOUNCE_MS=20)(
    input wire clk,rst_n,button_n, output reg press
);
    localparam integer LIMIT=(CLK_HZ/1000)*DEBOUNCE_MS;
    localparam integer CW=(LIMIT<2)?1:$clog2(LIMIT+1);
    reg sync0,sync1,stable,qualified;
    reg [CW-1:0] count;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            // A held button during configuration must never auto-start the
            // vehicle.  Qualification is granted only after a debounced
            // released level has been observed.
            sync0<=1;sync1<=1;stable<=1;qualified<=0;count<=0;press<=0;
        end
        else begin
            sync0<=button_n;sync1<=sync0;press<=0;
            if(sync1==stable) begin
                count<=0;
            end
            else if(count==LIMIT-1) begin
                stable<=sync1;count<=0;
                if(stable && !sync1 && qualified) press<=1;
                // This high level has already passed the debounce interval;
                // it is the first valid release qualification.
                if(sync1) qualified<=1;
            end else count<=count+1'b1;
        end
endmodule
`default_nettype wire
