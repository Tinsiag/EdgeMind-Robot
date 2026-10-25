`timescale 1ns/1ps
module motion_sync_profile_tb;
    reg clk=0,rstn=0;
    reg [7:0] ct;
    reg [255:0] cp;
    wire li1,li2,ri1,ri2;
    always #5 clk=~clk;
    // The same parameters as the release wrapper, with a faster simulation timebase.
    motion_top #(.CLK_HZ(1000000),.PWM_HZ(1000),.PI_LIMIT_DEFAULT(512),
        .RAMP_LIMIT_DEFAULT(50),.CALIBRATED_DEFAULTS(1),.ENCODER_FAULT_ENABLE(0),
        .RIGHT_BRIDGE_INVERT(1),.MOTION_CAPABILITIES(1)) dut(
        .clk(clk),.stop_n(rstn),.uart_rx(1'b1),.uart_tx(),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(li1),.left_in2(li2),.right_in1(ri1),.right_in2(ri2),.led());
    task cmd;input[7:0] t;input[255:0] p;begin
        @(negedge clk);ct=t;cp=p;
        force dut.cmd_type=ct;force dut.payload=cp;force dut.cmd_ttl=16'd250;force dut.cmd_valid=1'b1;
        @(negedge clk);release dut.cmd_valid;release dut.cmd_type;release dut.payload;release dut.cmd_ttl;
        repeat(2) @(negedge clk);
    end endtask
    initial begin
        repeat(4) @(negedge clk);rstn=1;repeat(12) @(negedge clk);
        if(dut.cpr_l!=1469 || dut.cpr_r!=1471 || dut.pi_limit!=512 || dut.ramp_limit!=50 || dut.params_valid!=127)
            $fatal(1,"calibrated reset defaults missing");
        if(dut.armed || li1 || li2 || ri1 || ri2) $fatal(1,"reset started motion");
        cmd(8'h02,0);if(!dut.armed) $fatal(1,"ARM defaults failed");
        force dut.left_invalid=1'b1;repeat(3) @(negedge clk);release dut.left_invalid;
        repeat(3) @(negedge clk);if(dut.faults!=0) $fatal(1,"illegal AB mask lost");
        cmd(8'h11,(256'd100<<32)|256'd100);
        repeat(12000) @(negedge clk);
        if(dut.pi_l<=0 || dut.pi_r<=0 || dut.target_r!=100) $fatal(1,"positive feedback frame changed");
        cmd(8'h04,0);repeat(4) @(negedge clk);
        if(dut.armed || li1 || li2 || ri1 || ri2) $fatal(1,"STOP failed");
        cmd(8'h02,0);cmd(8'h11,(256'd100<<32)|256'd100);
        force dut.command_age=16'd251;repeat(2) @(negedge clk);release dut.command_age;
        repeat(4) @(negedge clk);if(!dut.faults[0] || dut.armed || li1 || li2 || ri1 || ri2) $fatal(1,"TTL failed");
        rstn=0;repeat(4) @(negedge clk);rstn=1;repeat(12) @(negedge clk);
        cmd(8'h02,0);cmd(8'h11,256'd100);
        repeat(210000) @(negedge clk);
        if(!dut.faults[2] || dut.armed || li1 || li2 || ri1 || ri2) $fatal(1,"no-feedback protection failed");
        $display("PASS A723 reset/ARM/masked illegal AB/positive targets/STOP/TTL/no-feedback");$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
