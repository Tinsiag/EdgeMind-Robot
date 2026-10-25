`timescale 1ns/1ps
module map_udp_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;reg [7:0] rx_data=0;reg rx_valid=0,rx_last=0,rx_bad=0;
    wire rx_ready;wire [7:0] tx_data;wire tx_valid,tx_last;wire [15:0] tx_length;reg tx_ready=0;
    wire command;reg command_ready=1;wire [7:0] kind;wire [255:0] payload;
    reg reply_done=0;reg [255:0] reply=256'habcdef00;wire waiting;
    a741_map_udp dut(.*);
    reg [7:0] bytes[0:63],received[0:63];reg [15:0] crc;integer i,count=0,accepted=0;
    reg [255:0] expected_payload=256'h01000000;
    function [15:0] update_crc(input [15:0] old,input [7:0] data);
        reg [15:0] v;integer n;begin v=old^{data,8'd0};for(n=0;n<8;n=n+1) v=v[15] ? (v<<1)^16'h1021:v<<1;update_crc=v;end
    endfunction
    always @(posedge clk) begin
        reply_done<=command;
        if(command) begin
            accepted<=accepted+1;
            if(kind!=8'h51 || payload!==expected_payload) $fatal(1,"map command decode");
        end
        if(tx_valid && tx_ready) begin received[count]<=tx_data;count<=count+1;end
    end
    task send(input [7:0] k,input corrupt);
        begin
            bytes[0]="E";bytes[1]="M";bytes[2]="M";bytes[3]="1";
            bytes[4]=1;bytes[5]=0;bytes[6]=0;bytes[7]=0;bytes[8]=k;bytes[9]=4;
            bytes[10]=0;bytes[11]=0;bytes[12]=0;bytes[13]=1;
            crc=65535;for(i=0;i<14;i=i+1) crc=update_crc(crc,bytes[i]);bytes[14]=crc[7:0];bytes[15]=crc[15:8]^(corrupt ? 1:0);
            for(i=0;i<16;i=i+1) begin @(negedge clk);rx_data=bytes[i];rx_valid=1;rx_last=i==15;end
            @(negedge clk);rx_valid=0;rx_last=0;repeat(35) @(negedge clk);
        end
    endtask
    task transmit(input integer size,input integer bad_index);
        begin
            for(i=0;i<size;i=i+1) begin
                @(negedge clk);rx_data=bytes[i];rx_valid=1;rx_last=i==size-1;rx_bad=i==bad_index;
            end
            @(negedge clk);rx_valid=0;rx_last=0;rx_bad=0;repeat(5) @(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;send(8'h51,1);if(accepted!=0 || tx_valid) $fatal(1,"bad CRC accepted");
        send(8'h55,0);if(accepted!=0 || tx_valid) $fatal(1,"motion command on map port accepted");
        send(8'h51,0);wait(tx_valid);#1;
        if(tx_length!=44 || tx_data!="E") $fatal(1,"map reply envelope");
        repeat(10) begin @(negedge clk);if(tx_data!="E" || !tx_valid) $fatal(1,"map reply unstable under backpressure");end
        tx_ready=1;wait(count==44);@(negedge clk);tx_ready=0;
        crc=65535;for(i=0;i<42;i=i+1) crc=update_crc(crc,received[i]);
        if(crc!={received[43],received[42]} || received[8]!=8'hd0 || received[9]!=32 || received[10]!=0 || received[13]!=8'hab)
            $fatal(1,"map reply contents/CRC");
        if(accepted!=1) $fatal(1,"map command executed more than once");
        // Truncation, transport errors and busy arbitration cannot issue writes.
        transmit(14,-1);transmit(16,8);command_ready=0;transmit(16,-1);command_ready=1;
        if(accepted!=1) $fatal(1,"incomplete/bad/busy map command accepted");
        // Maximum 24-byte map write; all payload bytes must retain their order.
        bytes[9]=28;bytes[10]=1;bytes[13]=24;expected_payload=0;
        for(i=14;i<38;i=i+1) bytes[i]=i^8'had;
        for(i=0;i<28;i=i+1) expected_payload[i*8+:8]=bytes[10+i];
        crc=65535;for(i=0;i<38;i=i+1) crc=update_crc(crc,bytes[i]);bytes[38]=crc[7:0];bytes[39]=crc[15:8];
        count=0;transmit(40,-1);if(accepted!=2 || !tx_valid) $fatal(1,"maximum map payload rejected");
        // A packet begins while the reply is stalled, then extends beyond the
        // end of that reply. Its tail must not become a fresh map datagram.
        @(negedge clk);rx_valid=1;rx_data=0;rx_last=0;
        repeat(3) @(negedge clk);tx_ready=1;
        wait(count==44);@(negedge clk);tx_ready=0;
        for(i=0;i<40;i=i+1) begin @(negedge clk);rx_data=bytes[i];rx_last=i==39;end
        @(negedge clk);rx_valid=0;rx_last=0;repeat(5) @(negedge clk);
        if(accepted!=2 || tx_valid) $fatal(1,"busy packet tail accepted");
        count=0;transmit(40,-1);if(accepted!=3 || !tx_valid) $fatal(1,"recovery after busy packet");
        tx_ready=1;wait(count==44);@(negedge clk);tx_ready=0;
        crc=65535;for(i=0;i<42;i=i+1) crc=update_crc(crc,received[i]);
        if(crc!={received[43],received[42]}) $fatal(1,"maximum request response CRC");
        $display("PASS dedicated map UDP CRC, whitelist, truncation/errors/arbitration, maximum payload, busy packet boundary and reply backpressure");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
