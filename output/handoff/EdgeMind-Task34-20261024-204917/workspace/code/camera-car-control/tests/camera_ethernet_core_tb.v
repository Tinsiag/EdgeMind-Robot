`timescale 1ns/1ps
module camera_ethernet_core_tb;
    reg clk=0,net_clk=0,pclk=0,rst_n=0;
    reg [7:0] rx_data=0,cam_data=0;
    reg rx_valid=0,rx_last=0,href=0,vsync=1,tx_ready=0;
    wire rx_ready,tx_valid,tx_last,tx_bad;
    wire [7:0] tx_data;
    integer outfile,index=0,bytes=0,cycles=0,nvectors;
    reg [15:0] vectors[0:4095];
    reg [1023:0] input_path,output_path;
    always #10 clk=~clk;
    always #4 net_clk=~net_clk;
    always #20 pclk=~pclk;
    camera_ethernet_core #(.WIDTH(4),.HEIGHT(2),.SKIP_FRAMES(0)) dut(
        .clk_50m(clk),.stop_n(rst_n),.net_clk(net_clk),.eth_rx_data(rx_data),
        .eth_rx_valid(rx_valid),.eth_rx_last(rx_last),.eth_rx_bad(1'b0),.eth_rx_ready(rx_ready),
        .eth_tx_data(tx_data),.eth_tx_valid(tx_valid),.eth_tx_last(tx_last),.eth_tx_bad(tx_bad),.eth_tx_ready(tx_ready),
        .cam_pclk(pclk),.cam_ready(1'b1),.cam_vsync(vsync),.cam_href(href),.cam_data(cam_data),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(),.left_in2(),.right_in1(),.right_in2(),.motion_led(),.camera_bad(),.camera_overflow());
    // Match 400ns serial bits across the independent 125MHz/50MHz clocks.
    defparam dut.control.sender.CLK_HZ=5760000;
    defparam dut.control.receiver.CLK_HZ=5760000;
    defparam dut.camera_motion.motion.controller.u_rx.CLK_HZ=2304000;
    defparam dut.camera_motion.motion.controller.st.u_tx.CLK_HZ=2304000;
    always @(negedge net_clk) begin cycles=cycles+1;tx_ready=cycles%7!=0;end
    always @(posedge net_clk) if(tx_valid && tx_ready) begin
        if(tx_bad) $fatal(1,"FAIL bad Ethernet output frame");
        $fwrite(outfile,"%02x",tx_data);bytes=bytes+1;
        if(tx_last) $fwrite(outfile,"\n");
    end
    task pixel;
        begin
            @(negedge pclk);href=1;cam_data=8'hf8;
            @(negedge pclk);cam_data=8'h00;
        end
    endtask
    task camera_frame;
        integer row,x;
        begin
            #50000;
            @(negedge pclk);vsync=0;
            repeat(3) @(negedge pclk);
            for(row=0;row<2;row=row+1) begin
                for(x=0;x<4;x=x+1) pixel();
                @(negedge pclk);href=0;
                repeat(3) @(negedge pclk);
            end
            vsync=1;
        end
    endtask
    initial begin
        if(!$value$plusargs("INPUT=%s",input_path)) $fatal(1,"Missing input vectors");
        if(!$value$plusargs("DUMP=%s",output_path)) $fatal(1,"Missing output path");
        if(!$value$plusargs("COUNT=%d",nvectors)) $fatal(1,"Missing vector count");
        $readmemh(input_path,vectors,0,nvectors-1);
        outfile=$fopen(output_path,"w");
        repeat(12) @(negedge clk);rst_n=1;
        fork
            camera_frame();
            begin
                while(vectors[index]!=16'hffff) begin
                    if(vectors[index]==16'h1000) #250000;
                    else if(vectors[index]==16'h2000) begin
                        if(!dut.camera_motion.motion.controller.armed) $fatal(1,"FAIL ARM was not delivered");
                    end else if(vectors[index]==16'h3000) begin
                        if(dut.camera_motion.motion.controller.target_l!=100 ||
                           dut.camera_motion.motion.controller.target_r!=100) $fatal(1,"FAIL velocity not delivered");
                    end else if(vectors[index]==16'h4000) begin
                        if(dut.camera_motion.motion.controller.armed ||
                            dut.camera_motion.motion.controller.target_l ||
                            dut.camera_motion.motion.controller.target_r) $fatal(1,"FAIL STOP or stale command rejection");
                    end else begin
                        @(negedge net_clk);rx_data=vectors[index][7:0];rx_last=vectors[index][8];rx_valid=1;
                        @(posedge net_clk);while(!rx_ready) @(posedge net_clk);
                        @(negedge net_clk);rx_valid=0;rx_last=0;
                    end
                    index=index+1;
                end
            end
        join
        #250000;
        if(bytes<250) $fatal(1,"FAIL insufficient Ethernet replies");
        if(dut.control.rejected<3) $fatal(1,"FAIL invalid EMC1 accepted");
        $fclose(outfile);
        $display("PASS camera_ethernet_core: full Ethernet ingress/egress and stale motion rejection");
        $finish;
    end
    initial begin #8000000;$fatal(1,"FAIL network integration timeout");end
    initial begin
        #1000;$display("Network simulation started");
        forever begin #250000;$display("Network progress: t=%0t vector=%0d state=%0d bytes=%0d",$time,index,dut.control.state,bytes);end
    end
endmodule
