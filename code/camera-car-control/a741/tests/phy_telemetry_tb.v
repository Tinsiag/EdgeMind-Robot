`timescale 1ns/1ps
module phy_telemetry_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,ms=0,ready=0;
    reg [255:0] phy_snapshot={8'd10,8'd50,8'd5,8'd0,8'd0,8'd1,
        16'h796d,16'h7949,16'h1140,32'h001cc916,32'd456,32'd123,16'd32,16'd1,32'h31504d45};
    wire [7:0] data;wire valid,last;wire [15:0] length;wire [31:0] dropped;
    a741_telemetry #(.PHY_DIAGNOSTICS(1)) dut(.clk(clk),.rst_n(rst),.ms_tick(ms),
        .snapshot(896'd0),.phy_snapshot(phy_snapshot),.lidar_update(1'b0),
        .lidar_packet(376'd0),.lidar_time(32'd0),.lidar_seq(32'd0),
        .data(data),.valid(valid),.last(last),.length(length),.ready(ready),.dropped(dropped));
    reg [255:0] expected;
    integer i;
    initial begin
        #50;rst=1;
        repeat(1000) begin @(negedge clk);ms=1;@(negedge clk);ms=0;end
        if(!valid || length!=112) $fatal(1,"stalled EMS1 not retained");
        ready=1;
        repeat(112) @(negedge clk);
        ready=0;wait(valid);@(negedge clk);
        if(length!=32 || data!="E") $fatal(1,"PHY diagnostic starved by snapshot");
        expected=phy_snapshot;phy_snapshot=0;
        repeat(20) begin @(negedge clk);if(data!="E" || !valid) $fatal(1,"PHY stall not atomic");end
        ready=1;
        for(i=0;i<32;i=i+1) begin
            if(data!==expected[i*8+:8] || last!=(i==31)) $fatal(1,"PHY packet offset %d",i);
            @(negedge clk);
        end
        ready=0;wait(valid);@(negedge clk);
        if(length!=112 || dropped!=0) $fatal(1,"EMS1 schedule not preserved");
        $display("PASS EMP1 exact byte layout, 1Hz scheduling, backpressure atomicity and EMS1 resume");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
