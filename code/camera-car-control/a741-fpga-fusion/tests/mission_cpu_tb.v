`timescale 1ns/1ps
module mission_cpu_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,armed=0,geometry_verified=1,nav_busy=0,nav_arrived=0,nav_failed=0;
    reg host_command=0;reg [7:0] host_kind=8'h58;reg [255:0] host_payload=0;
    wire host_reply_done,nav_command,owns,alive,fault;wire [255:0] host_reply,nav_payload;
    wire [7:0] nav_kind;wire [31:0] progress;
    reg nav_reply_done=0;reg [255:0] nav_reply=0;
    integer cycles=0,started=0,goals=0,age=0;
    wire ms_tick=cycles%50==49;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;
    a741_mission_cpu dut(.*);
    always @(posedge clk) begin
        nav_reply_done<=nav_command;
        if(nav_command && nav_kind==8'h54) begin
            if(nav_payload[7:0]!=64+goals%3 || nav_payload[15:8]!=64) $fatal(1,"waypoint order/payload incorrect");
            goals<=goals+1;nav_arrived<=0;
        end
        if(nav_command && nav_kind==8'h55) begin nav_busy<=1;started<=started+1;age<=0;end
        else if(nav_busy) begin
            age<=age+1;
            if(age==1000) begin nav_busy<=0;nav_arrived<=1;end
        end
    end
    task host(input [7:0] op,input [31:0] arg,input integer expected);
        integer timeout;
        begin
            @(negedge clk);host_payload={216'd0,arg,op};host_command=1;
            @(negedge clk);host_command=0;timeout=0;
            while(!host_reply_done && timeout<100000) begin @(negedge clk);timeout=timeout+1;end
            if(!host_reply_done || host_reply[7:0]!=expected) $fatal(1,"host op=%0d reply=%0d trap=%0d timeout=%0d",op,host_reply[7:0],dut.trap,timeout);
            @(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;wait(alive);
        host(0,0,0);host(1,32'h00004040,0);host(1,32'h00004041,0);host(1,32'h00004042,0);
        host(2,0,1);if(owns) $fatal(1,"unarmed mission accepted");
        armed=1;host(2,0,0);wait(owns);wait(started==3);wait(!owns);repeat(100) @(negedge clk);
        if(fault || goals!=3 || progress[7:0]!=3 || progress[31:24]!=0) $fatal(1,"three-waypoint completion failed progress=%h",progress);
        host(2,0,0);wait(owns);
        force dut.mem_valid=0;
        repeat(5200) @(negedge clk);
        if(owns || !fault || alive) $fatal(1,"CPU watchdog did not revoke control owns=%0d alive=%0d fault=%0d age=%0d",owns,alive,fault,dut.watchdog);
        release dut.mem_valid;
        $display("PASS real RV32I firmware boot, armed gate, three waypoints without host heartbeat and CPU watchdog");$finish;
    end
    initial begin #30000000;$fatal(1,"mission CPU watchdog");end
endmodule
