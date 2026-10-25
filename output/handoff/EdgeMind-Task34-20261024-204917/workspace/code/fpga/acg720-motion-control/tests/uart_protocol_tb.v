`timescale 1ns/1ps
module uart_protocol_tb;
    reg clk=0,rstn=0,valid=0; reg [7:0] data=0; wire cmd_valid; wire [7:0] typ,seq; wire [15:0] ttl; wire [255:0] payload; wire crc_error,len_error;
    always #5 clk=~clk;
    motion_protocol dut(.clk(clk),.rstn(rstn),.rx_data(data),.rx_valid(valid),.cmd_valid(cmd_valid),.cmd_type(typ),.cmd_seq(seq),.cmd_ttl_ms(ttl),.cmd_payload(payload),.crc_error(crc_error),.length_error(len_error));
    task put(input [7:0] b); begin @(negedge clk); data=b; valid=1; @(negedge clk); valid=0; end endtask
    function [15:0] crc16; input [15:0] c; input [7:0] d; integer k; reg [15:0] x; begin x=c; for(k=0;k<8;k=k+1)x=(x[15]^d[7-k])?((x<<1)^16'h1021):(x<<1);crc16=x;end endfunction
    reg [15:0] crc; reg accepted;
    always @(posedge clk) if(cmd_valid) accepted=1;
    initial begin
        #20; rstn=1; crc=16'hffff;
        put(8'hAA);put(8'h55); put(1);crc=crc16(crc,1); put(8'h01);crc=crc16(crc,8'h01); put(0);crc=crc16(crc,0); put(7);crc=crc16(crc,7); put(8'd250);crc=crc16(crc,8'd250); put(0);crc=crc16(crc,0); put(crc[7:0]);put(crc[15:8]);
        #20; if(!accepted || typ!=8'h01 || seq!=7 || ttl!=250 || crc_error) $fatal(1,"protocol frame not accepted");
        $display("PASS protocol parser"); $finish;
    end
endmodule
