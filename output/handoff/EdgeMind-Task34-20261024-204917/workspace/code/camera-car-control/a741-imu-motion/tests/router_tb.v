`timescale 1ns/1ps
module router_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,cv=0,cl=0,tv=0,tl=0,vv=0,vl=0;
    wire cr,tr,vr;reg downstream=0;
    a741_router dut(.clk(clk),.rst_n(rst),
        .eth_rx_data(8'd0),.eth_rx_valid(1'b0),.eth_rx_last(1'b0),.eth_rx_bad(1'b0),.eth_tx_ready(1'b0),
        .control_rx_ready(1'b1),.control_tx_data(8'hcc),.control_tx_valid(cv),.control_tx_last(cl),
        .control_tx_length(16'd1),.control_tx_ready(cr),
        .telemetry_data(8'haa),.telemetry_valid(tv),.telemetry_last(tl),.telemetry_length(16'd2),.telemetry_ready(tr),
        .video_data(8'hbb),.video_valid(vv),.video_last(vl),.video_length(16'd3),.video_ready(vr));
    initial begin
        force dut.uhr=1'b1;force dut.upr=downstream;
        #50;rst=1;@(negedge clk);vv=1;
        wait(dut.tx_active);@(negedge clk);cv=1;tv=1;
        repeat(10) begin
            @(negedge clk);
            if(dut.tx_control || dut.tx_telemetry || dut.tx_length!=3 || dut.upd!=8'hbb) $fatal(1,"video packet preempted");
        end
        vl=1;downstream=1;@(negedge clk);vv=0;vl=0;downstream=0;
        wait(dut.tx_active);@(negedge clk);
        if(!dut.tx_control || dut.tx_telemetry || dut.tx_length!=1) $fatal(1,"control priority");
        cl=1;downstream=1;@(negedge clk);cv=0;cl=0;downstream=0;
        wait(dut.tx_active);@(negedge clk);
        if(dut.tx_control || !dut.tx_telemetry || dut.tx_length!=2 || dut.upd!=8'haa) $fatal(1,"telemetry priority");
        tl=1;downstream=1;@(negedge clk);tv=0;tl=0;
        $display("PASS control > telemetry > video, packet lock and length under backpressure");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
