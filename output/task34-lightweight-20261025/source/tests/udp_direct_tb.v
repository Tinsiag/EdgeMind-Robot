`timescale 1ns/1ps
module udp_direct_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,rx_valid=0,rx_last=0,rx_bad=0,tx_ready=0,reply_valid=0;
    reg [7:0] rx_data=0,reply_kind=8'hd0,reply_seq=8'h5a,reply_length=0;
    reg [255:0] reply_payload=0;
    wire rx_ready,tx_valid,tx_first,tx_last,command,reply_ready;
    wire [7:0] tx_data,kind,seq;wire [15:0] tx_length,ttl;wire [255:0] payload;
    wire [31:0] rejected;wire [3:0] diagnostic_state;
    a741_udp_direct #(.CLK_HZ(1000000),.REPLY_TIMEOUT_MS(1)) dut(.*);
    reg [7:0] packet[0:127],response[0:63];
    integer length,commands=0,i,j,n,before_count,cycles;
    reg [15:0] crc;reg [7:0] stalled_data;reg stalled=0,stalled_last;
    always @(posedge clk) if(command) begin
        commands=commands+1;
        if(seq!=8'h5a || ttl!=16'h1234) $fatal(1,"direct fields changed");
    end
    always @(posedge clk) if(rst_n) begin
        if((rx_ready && diagnostic_state!=0) || (reply_ready && diagnostic_state!=6) || (tx_valid && diagnostic_state!=8))
            $fatal(1,"legacy diagnostic code changed");
        if(stalled && (!tx_valid || tx_data!==stalled_data || tx_last!==stalled_last))
            $fatal(1,"response changed under backpressure");
        stalled=tx_valid && !tx_ready;stalled_data=tx_data;stalled_last=tx_last;
    end
    function [15:0] crc_byte(input [15:0] c,input [7:0] d);
        integer k;reg [15:0] v;
        begin v=c;for(k=7;k>=0;k=k-1) v=(v[15]^d[k]) ? (v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    task outer_crc;
        begin
            crc=65535;for(j=0;j<length-2;j=j+1) crc=crc_byte(crc,packet[j]);
            packet[length-2]=crc[7:0];packet[length-1]=crc[15:8];
        end
    endtask
    task make_packet(input [31:0] session,number,input [7:0] cmd,input integer size);
        begin
            for(j=0;j<128;j=j+1) packet[j]=0;
            packet[0]="E";packet[1]="M";packet[2]="C";packet[3]="1";
            for(j=0;j<4;j=j+1) begin packet[4+j]=session>>(8*j);packet[8+j]=number>>(8*j);end
            packet[12]=8'haa;packet[13]=8'h55;packet[14]=1;packet[15]=cmd;packet[16]=size;
            packet[17]=8'h5a;packet[18]=8'h34;packet[19]=8'h12;
            if(cmd==8'h51) begin packet[20]=1;packet[23]=size-4;end
            if(cmd==8'h58 && size==5) packet[20]=1;
            for(j=4;j<size;j=j+1) packet[20+j]=j^8'h9c;
            crc=65535;for(j=14;j<20+size;j=j+1) crc=crc_byte(crc,packet[j]);
            packet[20+size]=crc[7:0];packet[21+size]=crc[15:8];length=24+size;outer_crc;
        end
    endtask
    task send_packet(input integer bytes,input integer bad_index,input integer accepted);
        begin
            before_count=commands;
            for(i=0;i<bytes;i=i+1) begin
                @(negedge clk);rx_valid=1;rx_data=packet[i];rx_last=i==bytes-1;rx_bad=i==bad_index;
                if(!rx_ready) $fatal(1,"bridge not ready");
                @(posedge clk);#1;
                if(commands!=before_count) $fatal(1,"command before complete CRC validation");
                if(i%4==2) begin @(negedge clk);rx_valid=0;rx_last=0;rx_bad=0;end
            end
            @(negedge clk);rx_valid=0;rx_last=0;rx_bad=0;
            repeat(5) @(negedge clk);
            if(commands!=before_count+accepted) $fatal(1,"unexpected command count kind=%h got=%0d expected=%0d",packet[15],commands-before_count,accepted);
            if(accepted && payload[31:0]!=={packet[23],packet[22],packet[21],packet[20]} && packet[16]>=4)
                $fatal(1,"payload not transferred");
        end
    endtask
    task answer(input integer size,input [31:0] session,number);
        begin
            if(!reply_ready) $fatal(1,"reply not ready");
            reply_length=size;for(j=0;j<32;j=j+1) reply_payload[j*8+:8]=j^8'ha5;
            reply_valid=1;@(negedge clk);reply_valid=0;
            n=0;cycles=0;
            while(n<24+size) begin
                tx_ready=cycles%5>=2;cycles=cycles+1;
                @(posedge clk);
                if(tx_valid && tx_ready) begin
                    if(tx_length!=24+size || tx_first!=(n==0) || tx_last!=(n==23+size)) $fatal(1,"reply framing");
                    response[n]=tx_data;n=n+1;
                end
                @(negedge clk);
                if(cycles>200) $fatal(1,"reply stalled");
            end
            tx_ready=0;
            if({response[3],response[2],response[1],response[0]}!=32'h31434d45 ||
               {response[7],response[6],response[5],response[4]}!=session ||
               {response[11],response[10],response[9],response[8]}!=number ||
               response[12]!=8'haa || response[13]!=8'h55 || response[14]!=1 || response[15]!=8'hd0 ||
               response[16]!=size || response[17]!=8'h5a || response[18]!=0 || response[19]!=0) $fatal(1,"reply header");
            for(j=0;j<size;j=j+1) if(response[20+j]!=(j^8'ha5)) $fatal(1,"reply payload");
            crc=65535;for(j=14;j<20+size;j=j+1) crc=crc_byte(crc,response[j]);
            if({response[21+size],response[20+size]}!=crc) $fatal(1,"reply inner CRC");
            crc=65535;for(j=0;j<22+size;j=j+1) crc=crc_byte(crc,response[j]);
            if({response[23+size],response[22+size]}!=crc) $fatal(1,"reply outer CRC");
            repeat(2) @(negedge clk);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        make_packet(10,1,8'h02,0);send_packet(length,-1,0);
        make_packet(10,1,8'h04,0);send_packet(length,-1,1);answer(32,10,1);
        make_packet(10,1,8'h04,0);send_packet(length,-1,0);
        make_packet(10,0,8'h04,0);send_packet(length,-1,0);
        make_packet(10,2,8'h04,0);packet[length-1]=packet[length-1]^1;send_packet(length,-1,0);
        make_packet(10,2,8'h04,0);packet[20]=packet[20]^1;outer_crc;send_packet(length,-1,0);
        make_packet(10,2,8'h58,5);send_packet(length-2,-1,0);
        make_packet(10,2,8'h04,0);send_packet(length,6,0);
        make_packet(10,2,8'h04,0);packet[12]=0;outer_crc;send_packet(length,-1,0);
        make_packet(10,2,8'h04,1);send_packet(length,-1,0);
        make_packet(10,2,8'h59,0);send_packet(length,-1,0);
        make_packet(10,2,8'h51,33);send_packet(length,-1,0);
        make_packet(10,2,8'h04,0);length=length+1;outer_crc;send_packet(length,-1,0);
        make_packet(10,2,8'h58,5);send_packet(length,-1,1);answer(1,10,2);
        make_packet(10,3,8'h51,28);send_packet(length,-1,1);answer(32,10,3);
        make_packet(10,4,8'h05,0);send_packet(length,-1,1);
        make_packet(10,5,8'h11,8);send_packet(length,-1,1);
        make_packet(11,6,8'h02,0);send_packet(length,-1,0);
        make_packet(11,6,8'h04,0);send_packet(length,-1,1);answer(0,11,6);
        make_packet(11,7,8'h40,0);send_packet(length,-1,1);
        repeat(1010) @(negedge clk);if(!rx_ready) $fatal(1,"reply timeout did not recover");
        make_packet(11,8,8'h04,0);send_packet(length,-1,1);answer(32,11,8);
        $display("PASS direct EMC1 atomic commit, dual CRC, truncation/size/transport errors, replay/session rules, no-reply commands, maximum payload, timeout and reply backpressure");$finish;
    end
    initial begin #1000000;$fatal(1,"bridge watchdog");end
endmodule
