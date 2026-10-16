`timescale 1ns/1ps
module acg720_bridge_probe_duration_tb;
    reg clk=0;always #5 clk=~clk;
    reg stop_n=1,left_key_n=1,right_key_n=1;
    wire left_default,right_default,left_clamped;
    wire [7:0] led_default;
    // Reduced clock rate preserves the actual default 2000 ms parameter.
    acg720_bridge_probe #(.CLK_HZ(1000),.STARTUP_MS(1),.DEBOUNCE_MS(1)) normal(
        .clk(clk),.stop_n(stop_n),.left_key_n(left_key_n),.right_key_n(right_key_n),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(left_default),.right_in1(right_default),.left_in2(),.right_in2(),.camera_reset_n(),.led(led_default));
    acg720_bridge_probe #(.CLK_HZ(1000),.STARTUP_MS(1),.DEBOUNCE_MS(1),.PROBE_MS(4000)) clamped(
        .clk(clk),.stop_n(stop_n),.left_key_n(left_key_n),.right_key_n(right_key_n),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(left_clamped),.right_in1(),.left_in2(),.right_in2(),.camera_reset_n(),.led());
    task cycles(input integer n);
        integer i;
        begin for(i=0;i<n;i=i+1)begin @(posedge clk);#1;end end
    endtask
    integer count;
    initial begin
        cycles(20);@(negedge clk);left_key_n=0;
        count=0;
        while(!left_default && count<20) begin cycles(1);count=count+1;end
        if(!left_default || !left_clamped) $fatal(1,"Start missing");
        count=0;
        while(left_default && count<2100) begin
            if(left_default!==left_clamped || right_default) $fatal(1,"Clamp or channel mismatch");
            count=count+1;cycles(1);
        end
        if(count!=2000 || left_clamped || !led_default[5]) $fatal(1,"Default/capped duration %0d",count);
        cycles(2100);if(left_default||left_clamped) $fatal(1,"Held timeout restarted");
        $display("PASS A71A default 2000 ms and oversized-parameter 2000 ms cap, no repeated hold");$finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
