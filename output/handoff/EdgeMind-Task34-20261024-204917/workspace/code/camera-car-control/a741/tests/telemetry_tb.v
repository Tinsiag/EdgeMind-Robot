`timescale 1ns/1ps
module telemetry_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,ms=0,lu=0,ready=0;reg [895:0] snapshot=0;
    reg [375:0] lp=376'h123456;
    wire [7:0] data;wire valid,last;wire [15:0] length;wire [31:0] dropped;
    a741_telemetry dut(.clk(clk),.rst_n(rst),.ms_tick(ms),.snapshot(snapshot),
        .lidar_update(lu),.lidar_packet(lp),.lidar_time(32'd123),.lidar_seq(32'd77),
        .data(data),.valid(valid),.last(last),.length(length),.ready(ready),.dropped(dropped));
    integer i;reg [7:0] saved;
    initial begin
        for(i=0;i<112;i=i+1) snapshot[i*8+:8]=i;
        #50;rst=1;
        repeat(50) begin @(negedge clk);ms=1;@(negedge clk);ms=0;end
        wait(valid);@(negedge clk);saved=data;snapshot=0;
        repeat(30) begin @(negedge clk);if(data!=saved || length!=112 || !valid) $fatal(1,"unstable backpressure");end
        lu=1;@(negedge clk);lu=0;@(negedge clk);lu=1;@(negedge clk);lu=0;
        ready=1;
        for(i=0;i<112;i=i+1) begin
            if(data!=i || last!=(i==111)) $fatal(1,"snapshot atomic byte %d %d",i,data);
            @(negedge clk);
        end
        ready=0;wait(valid);@(negedge clk);
        if(length!=64 || data!="E" || dropped!=1) $fatal(1,"EML1 header or overrun");
        ready=1;@(negedge clk);if(data!="M") $fatal(1,"EML1 M");
        @(negedge clk);if(data!="L") $fatal(1,"EML1 L");
        @(negedge clk);if(data!="1") $fatal(1,"EML1 1");
        $display("PASS atomic snapshots, EML1 header, lidar drop count, arbitrary backpressure");$finish;
    end
    initial begin #50000;$fatal(1,"watchdog");end
endmodule
