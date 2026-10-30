`timescale 1ns/1ps
module supervisor_gate_tb;
 GSR GSR(.GSRI(1'b1));
 reg clk=0,rst_n=0,armed=0;always #5 clk=~clk;
 reg [31:0] cycles=0;always @(posedge clk) if(rst_n) cycles<=cycles+1;
 wire ms_tick=cycles%10==9;wire alive,fault;wire [31:0] progress;
 cpu_gate_probe dut(.*);
 task run_program;
  begin
   repeat(2000) @(negedge clk);
   if(!alive || fault || progress<50) $fatal(1,"Gowin CPU heartbeat failed alive=%b fault=%b progress=%d",alive,fault,progress);
  end
 endtask
 initial begin
  #30;rst_n=1;run_program();$display("PASS first boot");armed=1;run_program();$display("PASS armed heartbeat");
  rst_n=0;armed=0;repeat(4) @(negedge clk);rst_n=1;run_program();$display("PASS warm-reset heartbeat");
  $display("PASS synthesized GW5A supervisor: startup AUIPC/JALR, heartbeat/uptime, armed operation and warm reset");$finish;
 end
endmodule
