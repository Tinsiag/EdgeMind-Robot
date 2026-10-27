`timescale 1ns/1ps
module bare_cpu_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,armed=0;integer cycles=0;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;
    wire ms_tick=cycles%10==9;
    wire alive,fault;wire [31:0] progress;
    reg [31:0] held_read;
    a741_bare_cpu dut(.*);
    initial begin
        #30;rst_n=1;wait(alive);armed=1;
        repeat(5000) @(negedge clk);
        if(!alive || fault || progress<300) $fatal(1,"bare firmware heartbeat/uptime failed %0d",progress);
        force dut.mem_valid=0;
        repeat(1020) @(negedge clk);
        if(alive || !fault) $fatal(1,"CPU stall did not latch watchdog fault");
        release dut.mem_valid;repeat(300) @(negedge clk);
        if(alive || !fault) $fatal(1,"CPU automatically recovered without reset");
        // Exercise RAM stores even though the tiny supervisor needs no stack.
        // Keep the CPU reset and drive its bus to verify byte lanes and the
        // held read output required for Arora V's supported normal SP mode.
        rst_n=0;
        force dut.mem_valid=1;
        force dut.mem_addr=32'd8188;
        force dut.mem_wstrb=4'b1111;
        force dut.mem_wdata=32'h12345678;
        @(negedge clk);
        force dut.mem_wstrb=0;
        @(negedge clk);
        if(dut.ram_q!==32'h12345678) $fatal(1,"RAM full store/load failed");
        // Read a different word before storing, so read-before-write inference
        // would visibly change ram_q during the partial store.
        force dut.mem_addr=32'd8184;
        @(negedge clk);held_read=dut.ram_q;
        force dut.mem_addr=32'd8188;
        force dut.mem_wstrb=4'b0101;
        force dut.mem_wdata=32'haabbccdd;
        @(negedge clk);
        if(dut.ram_q!==held_read) $fatal(1,"RAM read changed on store cycle");
        force dut.mem_wstrb=0;
        @(negedge clk);
        if(dut.ram_q!==32'h12bb56dd) $fatal(1,"RAM byte stores failed");
        $display("PASS bare RV32I heartbeat, uptime, watchdog, fault latch and normal-mode byte RAM");$finish;
    end
    initial begin #2000000;$fatal(1,"bare CPU watchdog");end
endmodule
