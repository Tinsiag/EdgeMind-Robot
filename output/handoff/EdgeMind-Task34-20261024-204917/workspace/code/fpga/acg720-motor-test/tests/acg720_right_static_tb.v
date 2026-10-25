`timescale 1ns/1ps
module acg720_right_static_tb;
    reg clk=0, clock_running=1; always #5 if(clock_running)clk=~clk;
    reg stop_n=1, left_key_n=1, right_key_n=1;
    reg left_enc_a=0, left_enc_b=0, right_enc_a=0, right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;
    wire [7:0] led;
    acg720_right_static #(.CLK_HZ(10000)) dut(.*);
    task check_fixed;
        begin
            if(right_in1!==1 || right_in2!==0 || left_in1!==0 || left_in2!==0 || camera_reset_n!==0)
                $fatal(1,"Fixed physical outputs changed");
            if(led[2:1]!==2'b10) $fatal(1,"Wrong fixed-output indication");
        end
    endtask
    integer pattern,n;
    reg heartbeat_seen=0;
    always @(posedge clk) begin
        #1;check_fixed;
        if(led[7])heartbeat_seen=1;
    end
    initial begin
        #1;check_fixed; // No startup gate, key press or timer required.
        // Exercise every combination of S0/S1/S2 and encoder levels, including
        // S0 held and both keys held. The requested output must stay 1/0.
        for(pattern=0;pattern<128;pattern=pattern+1)begin
            @(negedge clk);#1;
            {stop_n,left_key_n,right_key_n,left_enc_a,left_enc_b,right_enc_a,right_enc_b}=pattern;
            #1;check_fixed;
            for(n=0;n<257;n=n+1)begin @(posedge clk);#1;check_fixed;end
        end
        if(!heartbeat_seen)$fatal(1,"Status clock did not run");
        // Even a stopped clock cannot turn a constant output into PWM/zero.
        @(negedge clk);clock_running=0;
        #1000;check_fixed;
        $display("PASS A71C: immediate constant RAIN1=1/RAIN2=0 across all key/encoder combinations; other drive pins low, no PWM or timeout gating");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
