`timescale 1ns/1ps
module acg720_motor_hold_duration_tb;
    reg clk=0; always #5 clk=~clk;
    reg stop_n=1,left_key_n=1,right_key_n=1;
    reg left_enc_a=0,left_enc_b=0,right_enc_a=0,right_enc_b=0;
    wire left_in1,left_in2,right_in1,right_in2,camera_reset_n;
    wire [7:0] led;
    // 100 clocks per 1 kHz period: all production duty steps remain exact.
    // RUN_MS deliberately requests >1000 to verify the hard production cap.
    acg720_motor_hold_1khz_50 #(.CLK_HZ(100000),.STARTUP_MS(3),
        .DEBOUNCE_MS(2),.RUN_MS(1500)) dut(.*);
    task cycles(input integer n);
        integer i;begin for(i=0;i<n;i=i+1)begin @(posedge clk);#1;end end
    endtask
    integer side,n,period,phase,high_count,expected,total_high;
    initial begin
        cycles(1500);
        for(side=1;side<=2;side=side+1) begin
            @(negedge clk);left_key_n=(side!=1);right_key_n=(side!=2);
            n=0;while(!led[side] && n<1000)begin cycles(1);n=n+1;end
            if(!led[side])$fatal(1,"No start");
            total_high=0;
            for(period=0;period<1000;period=period+1) begin
                expected=period<50?10:(period<100?25:(period<200?40:50));
                high_count=0;
                for(phase=0;phase<100;phase=phase+1) begin
                    if(!led[side] || led[3-side])$fatal(1,"Enable duration/channel mismatch");
                    if((side==1?left_in1:right_in1))high_count=high_count+1;
                    if((side==1?right_in1:left_in1) || left_in2 || right_in2)
                        $fatal(1,"Wrong wheel/polarity");
                    cycles(1);
                end
                if(high_count!=expected)$fatal(1,"side=%0d period=%0d duty=%0d expected=%0d",side,period,high_count,expected);
                total_high=total_high+high_count;
            end
            if(led[2:1]!==0 || left_in1 || right_in1 || !led[5])
                $fatal(1,"1000ms hard timeout failed");
            if(total_high!=45750)$fatal(1,"Wrong total PWM exposure %0d",total_high);
            cycles(120000);
            if(led[2:1]!==0 || left_in1 || right_in1)$fatal(1,"Held key repeated");
            @(negedge clk);left_key_n=1;right_key_n=1;cycles(1000);
        end
        $display("PASS A71B: both wheels, every 1kHz period exact 10/25/40/50%% duty, 1000ms cap despite RUN_MS=1500, held-key no repeat");
        $finish;
    end
    initial begin #6000000;$fatal(1,"Watchdog");end
endmodule
