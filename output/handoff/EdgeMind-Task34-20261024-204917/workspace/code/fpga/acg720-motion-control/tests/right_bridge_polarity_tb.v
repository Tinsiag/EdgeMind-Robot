`timescale 1ns/1ps
module right_bridge_polarity_tb;
    reg clk=0,rstn=0;
    wire ri1,ri2,li1,li2;
    always #5 clk=~clk;
    motion_top #(.CLK_HZ(1000000),.PWM_HZ(1000),.RIGHT_BRIDGE_INVERT(1)) dut(
        .clk(clk),.stop_n(rstn),.uart_rx(1'b1),.uart_tx(),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(li1),.left_in2(li2),.right_in1(ri1),.right_in2(ri2),.led()
    );
    integer right1_high,right2_high,i;
    task sample_positive;
        begin
            force dut.control_enable=1'b1;force dut.pi_r=32'sd512;force dut.pi_l=32'sd0;
            repeat(3002) @(negedge clk);right1_high=0;right2_high=0;
            for(i=0;i<1000;i=i+1) begin
                @(negedge clk);if(ri1) right1_high=right1_high+1;if(ri2) right2_high=right2_high+1;
            end
            if(right1_high!=0 || right2_high!=500) $fatal(1,"positive right target: IN1=%0d IN2=%0d",right1_high,right2_high);
            if(li1||li2) $fatal(1,"zero left command drove bridge");
            release dut.pi_r;release dut.pi_l;
        end
    endtask
    task sample_negative;
        begin
            force dut.control_enable=1'b1;force dut.pi_r=-32'sd512;force dut.pi_l=32'sd0;
            repeat(3002) @(negedge clk);right1_high=0;right2_high=0;
            for(i=0;i<1000;i=i+1) begin
                @(negedge clk);if(ri1) right1_high=right1_high+1;if(ri2) right2_high=right2_high+1;
            end
            if(right1_high!=500 || right2_high!=0) $fatal(1,"negative right target: IN1=%0d IN2=%0d",right1_high,right2_high);
            if(li1||li2) $fatal(1,"zero left command drove bridge");
            release dut.pi_r;release dut.pi_l;release dut.control_enable;
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);rstn=1;
        sample_positive();sample_negative();
        $display("PASS right bridge inversion occurs after PI for positive/negative feedback coordinates");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
