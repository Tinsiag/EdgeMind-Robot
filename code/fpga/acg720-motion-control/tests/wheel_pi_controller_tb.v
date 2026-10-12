`timescale 1ns/1ps
module wheel_pi_controller_tb;
    reg clk=0,rstn=0,update=0,enable=0; reg signed [31:0] target=0,measured=0; wire signed [31:0] command,applied;
    always #5 clk=~clk;
    wheel_pi_controller #(.RAMP_LIMIT(100)) dut(.clk(clk),.rstn(rstn),.update(update),.enable(enable),.target_speed(target),.measured_speed(measured),.output_limit(1000),.ramp_limit(100),.command(command),.applied_target(applied));
    task tick; begin @(negedge clk); update=1; @(negedge clk); update=0; end endtask
    initial begin #20; rstn=1; enable=1; target=500; repeat(8) tick; if(command<=0) $fatal(1,"PI did not respond"); measured=500; repeat(12) tick; if(command>200) $fatal(1,"PI did not settle command=%0d",command); enable=0; tick; if(command!=0) $fatal(1,"disable failed"); $display("PASS PI command=%0d",command); $finish; end
endmodule
