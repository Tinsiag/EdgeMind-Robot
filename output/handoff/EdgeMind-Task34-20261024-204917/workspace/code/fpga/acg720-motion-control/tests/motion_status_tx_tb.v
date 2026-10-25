`timescale 1ns/1ps
module motion_status_tx_tb;
    reg clk=0, rstn=0, request=0, capabilities_request=0;
    reg [7:0] seq=1;
    wire tx;
    wire [7:0] rx_data;
    wire rx_valid, framing_error;
    reg [7:0] expected [0:34];
    integer received=0, i, expected_total=35;
    reg [15:0] crc;
    always #5 clk=~clk;
    motion_status_tx #(.CLK_HZ(5000000),.BAUD(100000)) dut(
        .clk(clk),.rstn(rstn),.request(request),.capabilities_request(capabilities_request),.request_seq(seq),
        .state_code(8'h03),.faults(16'h1234),
        .left_count(32'h12345678),.right_count(-32'sd2),
        .left_speed(32'd42),.right_speed(-32'sd42),
        .left_pwm(16'h0123),.right_pwm(16'h0234),.command_age(16'h4567),.tx(tx));
    uart_rx #(.CLK_HZ(5000000),.BAUD(100000)) receiver(
        .clk(clk),.rstn(rstn),.rx(tx),.data(rx_data),.valid(rx_valid),.framing_error(framing_error));
    function [15:0] crc_byte;
        input [15:0] c; input [7:0] d;
        integer k; reg [15:0] x;
        begin
            x=c ^ {d,8'h00};
            for(k=0;k<8;k=k+1) x=x[15] ? (x<<1)^16'h1021 : x<<1;
            crc_byte=x;
        end
    endfunction
    always @(posedge clk) if(rstn) begin
        if(framing_error) $fatal(1,"UART framing error");
        if(rx_valid) begin
            if(received>=expected_total) $fatal(1,"Extra byte");
            if(rx_data!==expected[received])
                $fatal(1,"Byte %0d got %h expected %h",received,rx_data,expected[received]);
            received=received+1;
        end
    end
    task check_reply;
        input [7:0] s;
        begin
            seq=s; received=0;
            expected[5]=s;
            crc=16'hffff;
            for(i=2;i<33;i=i+1) crc=crc_byte(crc,expected[i]);
            expected[33]=crc[7:0]; expected[34]=crc[15:8];
            @(negedge clk); request=1;
            @(negedge clk); request=0;
            wait(received==35);
            // Cover the final stop bit and ensure there is no extra byte.
            repeat(600) @(negedge clk);
        end
    endtask
    initial begin
        expected[0]=8'haa;expected[1]=8'h55;expected[2]=1;expected[3]=8'h80;expected[4]=25;
        expected[6]=0;expected[7]=0;expected[8]=3;expected[9]=8'h34;expected[10]=8'h12;
        expected[11]=8'h78;expected[12]=8'h56;expected[13]=8'h34;expected[14]=8'h12;
        expected[15]=8'hfe;expected[16]=8'hff;expected[17]=8'hff;expected[18]=8'hff;
        expected[19]=42;expected[20]=0;expected[21]=0;expected[22]=0;
        expected[23]=8'hd6;expected[24]=8'hff;expected[25]=8'hff;expected[26]=8'hff;
        expected[27]=8'h23;expected[28]=1;expected[29]=8'h34;expected[30]=2;
        expected[31]=8'h67;expected[32]=8'h45;
        repeat(4) @(negedge clk);rstn=1;
        check_reply(1);check_reply(2);check_reply(3);
        capabilities_request=1;seq=4;received=0;expected_total=18;
        expected[3]=8'hc0;expected[4]=8;expected[5]=4;
        expected[8]=8'h45;expected[9]=8'h56;expected[10]=8'h4d;expected[11]=8'h31;
        expected[12]=1;expected[13]=0;expected[14]=8'h90;expected[15]=1;
        crc=16'hffff;for(i=2;i<16;i=i+1) crc=crc_byte(crc,expected[i]);
        expected[16]=crc[7:0];expected[17]=crc[15:8];
        @(negedge clk);request=1;@(negedge clk);request=0;
        wait(received==18);repeat(600) @(negedge clk);
        $display("PASS STATUS: three complete 35-byte replies, sequence/payload/CRC verified");$finish;
    end
    initial begin #1000000;$fatal(1,"STATUS watchdog received=%0d",received);end
endmodule
