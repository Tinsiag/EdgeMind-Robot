`timescale 1ns/1ps
module fusion_network_tb;
    reg clk=0,rst=0;always #10 clk=~clk;
    reg [7:0] rx=0;reg valid=0,last=0,ready=0;
    wire rready,tvalid,tlast,tbad;wire [7:0] tx;wire l1,l2,r1,r2;
    a741_core #(.CLK_HZ(1152000),.FUSION_ENABLED(1),.MOTION_LIDAR(1)) dut(
        .clk(clk),.rst_n(rst),.imu_int(1'b0),.lidar_rx(1'b1),.mac_diagnostic(8'd0),.phy_ready(1'b1),.phy_error(1'b0),.phy_diagnostic(128'd0),
        .left_a(1'b0),.left_b(1'b0),.right_a(1'b0),.right_b(1'b0),.left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),
        .eth_rx_data(rx),.eth_rx_valid(valid),.eth_rx_last(last),.eth_rx_bad(1'b0),.eth_rx_ready(rready),
        .eth_tx_data(tx),.eth_tx_valid(tvalid),.eth_tx_last(tlast),.eth_tx_bad(tbad),.eth_tx_ready(ready),
        .video_data(8'd0),.video_valid(1'b0),.video_last(1'b0),.video_length(16'd0),
        .ddr_ready(1'b0),.frame_ready(1'b0),.camera_error(1'b0),.ddr_error(1'b0),.video_overflow(1'b0),.video_frames(32'd0));
    reg [15:0] vectors[0:8191];reg [2047:0] path,dump;integer count,i,fd,cycle=0;
    always @(negedge clk) begin cycle=cycle+1;ready=cycle%7!=0;end
    always @(posedge clk) begin
        if(l1 || l2 || r1 || r2) $fatal(1,"unverified fusion drove motor output");
        if(tvalid && ready) begin
            if(tbad) $fatal(1,"bad Ethernet output");
            $fwrite(fd,"%02x",tx);if(tlast) begin $fwrite(fd,"\n");$fflush(fd);end
        end
    end
    initial begin
        if(!$value$plusargs("INPUT=%s",path) || !$value$plusargs("DUMP=%s",dump) || !$value$plusargs("COUNT=%d",count)) $fatal(1,"vectors");
        $readmemh(path,vectors,0,count-1);fd=$fopen(dump,"w");repeat(12) @(negedge clk);rst=1;
        for(i=0;i<count;i=i+1) begin
            if(vectors[i]==16'h1000) #150000;
            else begin
                @(negedge clk);rx=vectors[i][7:0];last=vectors[i][8];valid=1;
                @(posedge clk);while(!rready) @(posedge clk);
                @(negedge clk);valid=0;last=0;
            end
        end
        #500000;$fclose(fd);$display("PASS integrated fusion Ethernet control/map/telemetry and zero motor outputs");$finish;
    end
    initial begin #12000000;$fatal(1,"watchdog");end
endmodule
