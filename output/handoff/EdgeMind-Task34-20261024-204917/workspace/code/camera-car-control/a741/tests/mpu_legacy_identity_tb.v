`timescale 1ns/1ps
module mpu_legacy_identity_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0;reg [31:0] now_ms=0;
    wire start,read;wire [6:0] address;wire [7:0] reg_addr;wire [3:0] byte_count;wire [111:0] write_data;
    reg busy=0,done=0;wire valid,ready;wire [7:0] fault,who_am_i;
    mpu6050_driver dut(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.now_ms(now_ms),
        .start(start),.read(read),.address(address),.reg_addr(reg_addr),.byte_count(byte_count),.write_data(write_data),
        .busy(busy),.done(done),.error(1'b0),.read_data(112'h70),
        .valid(valid),.ready(ready),.fault(fault),.who_am_i(who_am_i));
    integer cycle=0,low_reads=0,high_reads=0;
    always @(negedge clk) begin cycle=cycle+1;ms_tick=cycle%10==0;end
    always @(posedge clk) begin
        if(ms_tick) now_ms<=now_ms+1;
        done<=0;
        if(start) begin
            if(!read || reg_addr!=8'h75) $fatal(1,"default driver wrote unsupported device");
            if(address==7'h68) low_reads=low_reads+1;else high_reads=high_reads+1;
            busy<=1;
        end else if(busy) begin busy<=0;done<=1;end
    end
    initial begin
        #50;rst_n=1;wait(low_reads>0 && high_reads>0 && fault==2);repeat(3) @(negedge clk);
        if(ready || valid || who_am_i!=8'h70) $fatal(1,"non-test driver accepted MPU6500");
        $display("PASS default motion profile rejects MPU6500, probes both addresses and performs no writes");$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
