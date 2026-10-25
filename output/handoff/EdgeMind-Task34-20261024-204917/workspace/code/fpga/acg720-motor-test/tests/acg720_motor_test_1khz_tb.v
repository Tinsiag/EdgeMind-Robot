`timescale 1ns/1ps
module acg720_motor_test_1khz_tb;
    reg clk = 0;
    always #500 clk = ~clk; // 1 MHz simulation clock, 1000 cycles per 1 kHz period.
    reg stop_n = 1, left_key_n = 0, right_key_n = 1;
    reg left_enc_a = 0, left_enc_b = 0, right_enc_a = 0, right_enc_b = 0;
    wire left_in1, left_in2, right_in1, right_in2, camera_reset_n;
    wire [7:0] led;
    integer high_count, k, total;
`ifdef START50_TEST
    localparam EXPECT_HIGH = 500;
    acg720_motor_test_start50 #(
`else
    localparam EXPECT_HIGH = 250;
    acg720_motor_test_1khz #(
`endif
        .CLK_HZ(1000000), .STARTUP_MS(3), .DEBOUNCE_MS(2),
        .RUN_MS(20), .RAMP_MS(4)
    ) dut(.*);

    task cycles(input integer count);
        integer i;
        begin for (i=0; i<count; i=i+1) begin @(posedge clk); #1; end end
    endtask
    task idle;
        begin
            if (left_in1 !== 0 || right_in1 !== 0 || led[2:1] !== 0)
                $fatal(1, "Unexpected drive / busy");
        end
    endtask
    always @(posedge clk) begin
        #2;
        if (left_in2 !== 0 || right_in2 !== 0 || camera_reset_n !== 0)
            $fatal(1, "Unexpected reverse input or camera release");
        if ((left_in1 && right_in1) || led[2:1] == 2'b11)
            $fatal(1, "Both wheels driven");
    end
    initial begin
        cycles(9000); idle;
        @(negedge clk); left_key_n=1;
        cycles(5000); idle;
        @(negedge clk); left_key_n=0;
        total=0;
        while (!led[1] && total<5000) begin cycles(1); total=total+1; end
        if (!led[1]) $fatal(1, "Left start missing");
        cycles(6000);
        repeat(4) begin
            high_count=0;
            for (k=0; k<1000; k=k+1) begin
                cycles(1);
                if (left_in1) high_count=high_count+1;
                if (!led[1] || right_in1) $fatal(1, "Wrong wheel or early timeout");
            end
            if (high_count != EXPECT_HIGH) $fatal(1, "1 kHz PWM expected %0d/1000, got %0d", EXPECT_HIGH, high_count);
        end
        total=10000;
        while (led[1] && total<20500) begin cycles(1); total=total+1; end
        if (total<19900 || total>20002 || !led[5])
            $fatal(1, "Wrong bounded run timeout: %0d", total);
        cycles(5000); idle; // Held key must not repeat.
        @(negedge clk); left_key_n=1;
        cycles(5000);
        @(negedge clk); right_key_n=0;
        total=0;
        while (!led[2] && total<5000) begin cycles(1); total=total+1; end
        if (!led[2]) $fatal(1, "Right start missing");
        while (!right_in1) cycles(1);
        #10; stop_n=0; #1;
        if (right_in1 !== 0 || left_in1 !== 0) $fatal(1, "S0 not immediate");
        cycles(5);
        @(negedge clk); stop_n=1;
        cycles(9000); idle; // Held key cannot restart after reset.
        $display("PASS: 1 kHz wrapper, exact %0d/1000 duty, single-wheel timeout, held-key lockout and asynchronous stop", EXPECT_HIGH);
        $finish;
    end
    initial begin #100000000; $fatal(1, "Watchdog"); end
endmodule
