`timescale 1ns/1ps
module motion_core_tb;
    reg clk=0;always #5 clk=~clk;reg rst_n=0,enable=0,clear_fault=0;
    reg left_a=0,left_b=0,right_a=0,right_b=0;
    reg signed [31:0] left_target=100,right_target=100;
    reg [15:0] output_limit=512,ramp_limit=50;
    reg [31:0] cpr_l=1469,cpr_r=1471,diam_l=66,diam_r=66;
    wire left_in1,left_in2,right_in1,right_in2;
    wire signed [31:0] left_count,right_count,left_speed,right_speed;
    wire [15:0] left_pwm,right_pwm,faults;wire [31:0] left_invalid_count,right_invalid_count;wire ms_tick,control_tick;
    motion_core #(.CLK_HZ(1000000),.PWM_HZ(1000)) dut(.*);
    reg plant=0,reverse=0;integer ticks=0;reg [1:0] phase=0;
    always @(negedge clk)begin
        ticks=ticks+1;
        if(plant && enable && ticks%1500==0)begin
            phase=phase+1'b1;
            case(phase)
                0:begin {left_a,left_b}=0;{right_a,right_b}=0;end
                1:begin {left_a,left_b}=reverse?2:1;{right_a,right_b}=reverse?1:2;end
                2:begin {left_a,left_b}=3;{right_a,right_b}=3;end
                3:begin {left_a,left_b}=reverse?1:2;{right_a,right_b}=reverse?2:1;end
            endcase
        end
    end
    task reset;begin @(negedge clk);rst_n=0;enable=0;repeat(8)@(negedge clk);rst_n=1;repeat(10)@(negedge clk);enable=1;end endtask
    initial begin
        plant=1;reset;
        repeat(150000)@(negedge clk);
        if(left_count<=0 || right_count<=0 || left_speed<=0 || right_speed<=0 || faults!=0)$fatal(1,"Forward feedback sign/closed-loop path");
        if(left_pwm>512 || right_pwm>512)$fatal(1,"PI output cap");
        reverse=1;repeat(250000)@(negedge clk);
        if(!faults[3] || left_in1 || left_in2 || right_in1 || right_in2)$fatal(1,"Persistent reverse feedback not stopped");
        plant=0;reset;repeat(230000)@(negedge clk);
        if(!faults[2] || left_in1 || right_in2)$fatal(1,"No-feedback timeout missing");
        enable=0;clear_fault=1;@(negedge clk);clear_fault=0;
        if(faults!=0)$fatal(1,"Fault clear failed");
        $display("PASS: forward feedback, PI path/cap, persistent reverse fault and no-feedback stop");$finish;
    end
    initial begin #10000000;$fatal(1,"Watchdog");end
endmodule
