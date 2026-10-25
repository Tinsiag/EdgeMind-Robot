`timescale 1ns/1ps
module camera_motion_core_tb;
    reg clk=0,pclk=0,nclk=0,stop_n=0,uart_rx_line=1;
    reg vsync=1,href=0;
    reg [7:0] camera_data=0;
    wire uart_tx_line,l1,l2,r1,r2,bad,overflow;
    wire [7:0] led,data;
    wire valid,first,last;
    wire [15:0] length;
    integer count=0,packets=0,index,dump,uart_dump,uart_bytes=0;
    reg [7:0] bytes[0:1500];
    reg [1023:0] dump_path,uart_path;
    reg ready=0;
    always #10 clk=~clk;
    always #20 pclk=~pclk;
    always #4 nclk=~nclk;
    camera_motion_core #(.WIDTH(4),.HEIGHT(2),.SKIP_FRAMES(0),.FIFO_ADDR_BITS(6)) dut(
        .clk_50m(clk),.stop_n(stop_n),.uart_rx(uart_rx_line),.uart_tx(uart_tx_line),
        .left_enc_a(1'b0),.left_enc_b(1'b0),.right_enc_a(1'b0),.right_enc_b(1'b0),
        .left_in1(l1),.left_in2(l2),.right_in1(r1),.right_in2(r2),.motion_led(led),
        .cam_pclk(pclk),.cam_ready(1'b1),.cam_vsync(vsync),.cam_href(href),.cam_data(camera_data),
        .net_clk(nclk),.net_ready(ready),.video_udp_data(data),.video_udp_valid(valid),
        .video_udp_start(first),.video_udp_last(last),.video_udp_length(length),
        .camera_bad(bad),.camera_overflow(overflow));
    wire [7:0] reply;
    wire reply_valid;
    // Accelerate UART bit timing only; exercise the real framing/CRC logic.
    defparam dut.motion.controller.u_rx.CLK_HZ=1000000;
    defparam dut.motion.controller.st.u_tx.CLK_HZ=1000000;
    uart_rx #(.CLK_HZ(1000000)) monitor(.clk(clk),.rstn(stop_n),.rx(uart_tx_line),.data(reply),.valid(reply_valid),.framing_error());
    always @(posedge clk) if(reply_valid) begin $fwrite(uart_dump,"%02x",reply);uart_bytes=uart_bytes+1;end
    always @(posedge clk) if(stop_n && (l1 || l2 || r1 || r2)) $fatal(1,"FAIL unsolicited motor output");
    always @(posedge nclk) if(valid && ready) begin
        if(first && count!=0) $fatal(1,"FAIL overlapping packets");
        bytes[count]=data;count=count+1;
        if(last) begin
            if(count!=length) $fatal(1,"FAIL length");
            for(index=0;index<count;index=index+1) $fwrite(dump,"%02x",bytes[index]);
            $fwrite(dump,"\n");count=0;packets=packets+1;
        end
    end
    task camera_byte;
        input [7:0] value;
        begin @(negedge pclk);camera_data=value;href=1;end
    endtask
    task camera_frame;
        input integer short_row;
        integer row,p;
        begin
            @(negedge pclk);vsync=0;href=0;
            repeat(3) @(negedge pclk);
            for(row=0;row<2;row=row+1) begin
                for(p=0;p<(short_row && row==1 ? 3 : 4);p=p+1) begin
                    camera_byte(8'hf8);camera_byte(8'h00);
                end
                @(negedge pclk);href=0;
                repeat(3) @(negedge pclk);
            end
            vsync=1;
            repeat(5) @(negedge pclk);
        end
    endtask
    task uart_byte;
        input [7:0] value;
        integer bitno;
        begin
            uart_rx_line=0;#160;
            for(bitno=0;bitno<8;bitno=bitno+1) begin uart_rx_line=value[bitno];#160;end
            uart_rx_line=1;#160;
        end
    endtask
    initial begin
        if(!$value$plusargs("DUMP=%s",dump_path)) dump_path="core.hex";
        if(!$value$plusargs("UART=%s",uart_path)) uart_path="uart.hex";
        dump=$fopen(dump_path,"w");uart_dump=$fopen(uart_path,"w");
        repeat(10) @(negedge clk);stop_n=1;
        repeat(10) @(negedge pclk);
        fork
            begin
                camera_frame(0);camera_frame(1);
                #10000;ready=1;
            end
            begin
                // GET_CAPABILITIES seq=0x42 while the video endpoint is stalled.
                uart_byte(8'haa);uart_byte(8'h55);uart_byte(8'h01);uart_byte(8'h40);uart_byte(8'h00);
                uart_byte(8'h42);uart_byte(8'hfa);uart_byte(8'h00);uart_byte(8'h1f);uart_byte(8'hd5);
                #50000;
                // HELLO seq=0x43 returns a CRC-framed digital stopped status.
                uart_byte(8'haa);uart_byte(8'h55);uart_byte(8'h01);uart_byte(8'h01);uart_byte(8'h00);
                uart_byte(8'h43);uart_byte(8'hfa);uart_byte(8'h00);uart_byte(8'h16);uart_byte(8'h59);
            end
        join
        #100000;
        if(packets!=5 || overflow) $fatal(1,"FAIL packet count/overflow %0d %0d",packets,overflow);
        if(uart_bytes!=53) $fatal(1,"FAIL UART response count %0d",uart_bytes);
        $fclose(dump);$fclose(uart_dump);
        $display("PASS camera_motion_core: DVP/FIFO/UDP, bad frame, UART independence, no unsolicited PWM");
        $finish;
    end
    initial begin #1000000;$fatal(1,"FAIL core timeout");end
endmodule
