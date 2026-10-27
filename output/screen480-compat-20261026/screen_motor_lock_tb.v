`timescale 1ns/1ps
// Elaborate the generated screen-test top with Icarus -i (unrelated IP may be
// black boxes). Force all internal motor requests; physical pads must stay low.
module screen_motor_lock_tb;
    wire left_in1,left_in2,right_in1,right_in2;
    reg [3:0] requests=0;
    a741_top dut(.left_in1(left_in1),.left_in2(left_in2),
        .right_in1(right_in1),.right_in2(right_in2));
    integer pattern;
    initial begin
        force dut.global_n=1'b1;
        for(pattern=0;pattern<16;pattern=pattern+1) begin
            requests=pattern;
            // Re-issue force for each pattern: Icarus evaluates force RHS once.
            force dut.raw_l1=requests[0];force dut.raw_l2=requests[1];
            force dut.raw_r1=requests[2];force dut.raw_r2=requests[3];#10;
            if({dut.raw_r2,dut.raw_r1,dut.raw_l2,dut.raw_l1}!==requests)
                $fatal(1,"internal motor stimulus did not reach top-level wires");
            if({left_in1,left_in2,right_in1,right_in2}!==4'b0000)
                $fatal(1,"motor pads active at request %h",requests);
        end
        force dut.global_n=1'b0;#10;
        if({left_in1,left_in2,right_in1,right_in2}!==4'b0000) $fatal(1,"motor pads active in reset");
        $display("PASS generated top: motor pads remain low for every internal request and reset");
        $finish;
    end
endmodule
