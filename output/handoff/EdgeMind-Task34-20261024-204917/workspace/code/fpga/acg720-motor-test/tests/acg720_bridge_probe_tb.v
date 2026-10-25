`timescale 1ns/1ps
module acg720_bridge_probe_tb;
    reg clk=0; always #5 clk=~clk;
    reg stop_n=1, left_key_n=0, right_key_n=1;
    reg left_enc_a=0, left_enc_b=0, right_enc_a=0, right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;
    wire [7:0] led;
    acg720_bridge_probe #(.CLK_HZ(10000),.STARTUP_MS(3),.DEBOUNCE_MS(3),.PROBE_MS(7)) dut(.*);
    task cycles(input integer n);
        integer i;
        begin for(i=0;i<n;i=i+1) begin @(posedge clk); #1; end end
    endtask
    task low;
        begin if(left_in1!==0 || right_in1!==0) $fatal(1,"Unexpected output"); end
    endtask
    task release_keys;
        begin @(negedge clk); left_key_n=1;right_key_n=1;cycles(120);low; end
    endtask
    task wait_left;
        integer n;
        begin
            n=0; while(!left_in1 && n<100) begin cycles(1);n=n+1; end
            if(!left_in1 || right_in1 || !led[1]) $fatal(1,"Left start missing");
        end
    endtask
    task wait_right;
        integer n;
        begin
            n=0; while(!right_in1 && n<100) begin cycles(1);n=n+1; end
            if(!right_in1 || left_in1 || !led[2]) $fatal(1,"Right start missing");
        end
    endtask
    always @(posedge clk) begin
        #2;
        if(left_in2!==0 || right_in2!==0 || camera_reset_n!==0)
            $fatal(1,"Unexpected IN2 or camera release");
        if(left_in1 && right_in1) $fatal(1,"Two channels active");
        if((!stop_n || (!left_key_n && !right_key_n)) && (left_in1 || right_in1))
            $fatal(1,"Raw inhibit failed");
    end
    integer high_cycles;
    initial begin
        cycles(300);low; // A key held during configuration cannot start.
        release_keys;
        @(negedge clk);left_key_n=0;cycles(8);low;
        @(negedge clk);left_key_n=1;cycles(120);low; // Short bounce rejected.
        @(negedge clk);left_key_n=0;wait_left;
        high_cycles=0;
        while(left_in1 && high_cycles<100) begin high_cycles=high_cycles+1;cycles(1);end
        if(high_cycles!=70 || !led[5]) $fatal(1,"Hold duration %0d, expected 70 cycles",high_cycles);
        cycles(300);low; // Held key cannot repeat after timeout.
        @(negedge clk);left_key_n=1;right_key_n=0;cycles(150);low; // No release of BOTH keys.
        release_keys;
        @(negedge clk);right_key_n=0;wait_right;cycles(10);
        // Release must inhibit between clock edges, before debounce completes.
        @(negedge clk);#1;right_key_n=1;#1;low;
        cycles(2);@(negedge clk);right_key_n=0;cycles(150);low; // Release bounce cannot rearm.
        release_keys;
        @(negedge clk);left_key_n=0;right_key_n=0;cycles(120);low;
        if(!led[6]) $fatal(1,"Chord not indicated");
        @(negedge clk);right_key_n=1;cycles(150);low; // No leftover-key start.
        release_keys;
        @(negedge clk);left_key_n=0;wait_left;
        @(negedge clk);#1;right_key_n=0;#1;low; // Chord kills an active output immediately.
        cycles(5);@(negedge clk);right_key_n=1;cycles(150);low;
        release_keys;
        @(negedge clk);right_key_n=0;wait_right;
        @(negedge clk);#1;stop_n=0;#1;low; // S0 must not wait for a clock.
        cycles(5);@(negedge clk);stop_n=1;cycles(300);low; // Held key after S0 blocked.
        release_keys;
        @(negedge clk);right_key_n=0;wait_right;
        high_cycles=0;
        while(right_in1 && high_cycles<100) begin high_cycles=high_cycles+1;cycles(1);end
        if(high_cycles!=70 || !led[5]) $fatal(1,"Wrong right-channel duration");
        release_keys;
        @(negedge clk);left_enc_b=1;right_enc_a=1;
        cycles(5);if(led[4:3]!=2'b11) $fatal(1,"AB level indication incorrect");
        low;
        $display("PASS A71A: held-boot lockout, debounce, exact single-channel duration, timeout hold lockout, release/S0/chord immediate inhibit, rearm and LED mapping");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
