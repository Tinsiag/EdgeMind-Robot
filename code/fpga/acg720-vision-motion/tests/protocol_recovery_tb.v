`timescale 1ns/1ps
module protocol_recovery_tb;
    reg clk=0;always #5 clk=~clk;reg rstn=0,rx_valid=0;reg [7:0] rx_data=0;
    wire cmd_valid;wire [7:0] cmd_length,cmd_type,cmd_seq;wire [15:0] cmd_ttl_ms;
    wire [255:0] cmd_payload;wire crc_error,length_error;
    vision_protocol #(.CLK_HZ(1000000)) dut(.*);
    reg [15:0] crc;integer commands=0;
    always @(posedge clk)if(cmd_valid)commands=commands+1;
    function [15:0] crc_byte;input [15:0] c;input [7:0] d;reg [15:0] v;integer k;
        begin v=c;for(k=0;k<8;k=k+1)v=(v[15]^d[7-k])?((v<<1)^16'h1021):(v<<1);crc_byte=v;end
    endfunction
    task octet;input [7:0] v;begin @(negedge clk);rx_data=v;rx_valid=1;@(negedge clk);rx_valid=0;crc=crc_byte(crc,v);end endtask
    task stop_frame;begin
        octet(8'haa);octet(8'h55);crc=16'hffff;
        octet(1);octet(4);octet(0);octet(2);octet(250);octet(0);
        begin: send_crc reg [15:0] saved;saved=crc;octet(saved[7:0]);octet(saved[15:8]);end
        repeat(3)@(negedge clk);
    end endtask
    initial begin
        repeat(3)@(negedge clk);rstn=1;
        // An incomplete otherwise plausible command must not swallow later STOP.
        octet(8'haa);octet(8'h55);octet(1);octet(8'h11);octet(8);octet(1);
        repeat(21000)@(negedge clk);stop_frame;
        if(commands!=1 || cmd_type!=4 || cmd_length!=0)$fatal(1,"Partial-frame timeout/STOP recovery failed");
        // Repeated AA in noise must preserve the trailing header start.
        octet(8'haa);stop_frame;
        if(commands!=2)$fatal(1,"Repeated header recovery failed");
        $display("PASS: partial-frame timeout, STOP recovery and overlapping sync prefix");$finish;
    end
endmodule
