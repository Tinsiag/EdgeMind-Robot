`timescale 1ns/1ps
module ddr_readback_monitor_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0, ui_reset = 0, calibrated = 0;
    reg cmd_en = 0, cmd_ready = 1, wr_en = 0, wr_ready = 1;
    reg [2:0] cmd = 0;
    reg [27:0] addr = 0;
    reg [127:0] wr_data = 0, rd_data = 0;
    reg rd_valid = 0;
    wire passed, failed, timed_out;
    wire [4:0] checked_count;
    ddr_readback_monitor #(.TIMEOUT_BITS(5)) dut (.*);

    task tick;
        begin @(posedge clk); #1; @(negedge clk); end
    endtask
    task idle;
        begin cmd_en=0; wr_en=0; rd_valid=0; tick; end
    endtask
    task reset;
        begin
            rst_n=0; calibrated=0; cmd_en=0; wr_en=0; rd_valid=0;
            tick; rst_n=1; calibrated=1; tick;
        end
    endtask
    task write_word(input [27:0] a, input [127:0] d);
        begin
            cmd=0; addr=a; cmd_en=1; wr_en=1; wr_data=d;
            rd_valid=0; tick; cmd_en=0; wr_en=0;
        end
    endtask
    task read_cmd(input [27:0] a);
        begin cmd=1; addr=a; cmd_en=1; wr_en=0; rd_valid=0; tick; cmd_en=0; end
    endtask
    task response(input [127:0] d);
        begin cmd_en=0; wr_en=0; rd_data=d; rd_valid=1; tick; rd_valid=0; end
    endtask
    integer i;
    initial begin
        @(negedge clk); reset;
        // Prefetches before any observed write are not valid comparisons.
        read_cmd(0); response(128'hbad);
        if (passed || failed || checked_count != 0) $fatal(1,"prefetch checked");
        // No accepted write means no sample, despite asserted write enable.
        wr_ready=0; write_word(0,128'h111); wr_ready=1;
        read_cmd(0); response(128'h222);
        if (failed || checked_count != 0) $fatal(1,"unaccepted write sampled");
        // Two pending reads; the selected read must use the latest prior write.
        write_word(0,128'h123);
        read_cmd(256);
        write_word(0,128'h456);
        cmd_ready=0; read_cmd(0); cmd_ready=1;
        read_cmd(0);
        write_word(0,128'h789); // Later overwrite must not alter expectation.
        response(128'hbad); response(128'h456);
        if (failed || checked_count != 1) $fatal(1,"read ordering/snapshot");
        // Complete all remaining locations, with command/data activity together.
        for (i=1;i<16;i=i+1) begin
            write_word(i*8,128'hA500+i);
            read_cmd(i*8);
            cmd=1; addr=512; cmd_en=1; rd_valid=1; rd_data=128'hA500+i;
            tick; cmd_en=0; rd_valid=0;
            response(128'hcafe);
        end
        if (!passed || failed || checked_count != 16) $fatal(1,"full window");
        response(0); idle;
        if (!passed || failed) $fatal(1,"completed result not sticky");
        reset;
        write_word(0,128'hc001); read_cmd(0); response(128'hc000);
        if (!failed || passed || timed_out) $fatal(1,"corruption not detected");
        reset;
        write_word(0,128'h123); read_cmd(0);
        repeat (35) idle;
        if (!failed || !timed_out || passed) $fatal(1,"missing response timeout");
        reset;
        write_word(0,128'h123); read_cmd(0);
        ui_reset=1; tick; ui_reset=0;
        if (failed || passed || checked_count != 0) $fatal(1,"UI reset clear");
        // Wrap issue and return counters through ordinary accepted traffic.
        for (i=0;i<65535;i=i+1) begin read_cmd(256); response(i); end
        write_word(0,128'habcd); read_cmd(0); response(128'habcd);
        write_word(8,128'hdcba); read_cmd(8); response(128'hdcba);
        if (failed || checked_count != 2) $fatal(1,"sequence counter wrap");
        $display("PASS: prefetch, backpressure, overwrite, response ordering, concurrent traffic, 16 bursts, corruption, timeout, reset, sequence wrap");
        $finish;
    end
    initial begin #5000000; $fatal(1,"test watchdog"); end
endmodule
