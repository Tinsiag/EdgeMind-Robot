`timescale 1ns/1ps
module network_telemetry_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,ms=0,ready=0;
    reg [255:0] packet={32'd9,32'd43,32'd42,32'd123456,32'd1000,32'd5,16'd32,16'd1,32'h314e4d45};
    wire [7:0] data;wire valid,last;wire [15:0] length;wire [31:0] dropped;
    a741_telemetry #(.NETWORK_DIAGNOSTICS(1)) dut(.clk(clk),.rst_n(rst),.ms_tick(ms),
        .snapshot(896'd0),.phy_snapshot(packet),.lidar_update(1'b0),
        .lidar_packet(376'd0),.lidar_time(32'd0),.lidar_seq(32'd0),
        .data(data),.valid(valid),.last(last),.length(length),.ready(ready),.dropped(dropped));
    reg [255:0] expected;
    integer i;
    initial begin
        #50;rst=1;
        repeat(50) begin @(negedge clk);ms=1;@(negedge clk);ms=0;end
        wait(valid);@(negedge clk);
        if(length!=32) $fatal(1,"EMN1 must be scheduled at 50ms");
        expected=packet;packet=0;
        repeat(20) begin @(negedge clk);if(data!="E" || !valid) $fatal(1,"EMN1 stall");end
        ready=1;
        for(i=0;i<32;i=i+1) begin
            if(data!==expected[i*8+:8] || last!=(i==31)) $fatal(1,"EMN1 layout/atomicity %d",i);
            @(negedge clk);
        end
        ready=0;wait(valid);@(negedge clk);
        if(length!=112) $fatal(1,"EMS1 starved");
        $display("PASS EMN1 50ms scheduling, byte layout, atomic stalls and EMS1 compatibility");$finish;
    end
    initial begin #50000;$fatal(1,"watchdog");end
endmodule
