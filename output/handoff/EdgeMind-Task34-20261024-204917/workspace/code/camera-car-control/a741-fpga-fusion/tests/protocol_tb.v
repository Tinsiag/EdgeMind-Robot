`timescale 1ns/1ps
module protocol_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,valid=0;reg [7:0] data=0;
    wire cv,le;wire [7:0] kind;integer accepted=0,rejected=0;
    a741_protocol dut(.clk(clk),.rstn(rst),.rx_data(data),.rx_valid(valid),.cmd_valid(cv),.cmd_type(kind),.length_error(le));
    always @(posedge clk) begin if(cv) accepted=accepted+1;if(le) rejected=rejected+1;end
    reg [15:0] crc;reg [7:0] bytes[0:39];integer i,k;
    function [15:0] update_crc(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer n;
        begin v=c^{b,8'd0};for(n=0;n<8;n=n+1) v=v[15] ? (v<<1)^16'h1021:v<<1;update_crc=v;end
    endfunction
    task put(input [7:0] b);begin @(negedge clk);valid=1;data=b;@(negedge clk);valid=0;end endtask
    task send(input [7:0] version,input [7:0] command,input [7:0] length,input corrupt);
        begin
            bytes[0]=version;bytes[1]=command;bytes[2]=length;bytes[3]=1;bytes[4]=250;bytes[5]=0;
            for(i=6;i<length+6;i=i+1) bytes[i]=0;
            crc=16'hffff;for(i=0;i<length+6;i=i+1) crc=update_crc(crc,bytes[i]);
            put(8'haa);put(8'h55);for(i=0;i<length+6;i=i+1) put(bytes[i]);
            put(crc[7:0]);put(corrupt ? crc[15:8]^1:crc[15:8]);repeat(3) @(negedge clk);
        end
    endtask
    initial begin
        #50;rst=1;
        send(1,8'h42,0,0);send(2,4,0,0);send(1,8'h45,7,0);
        if(accepted || rejected!=3) $fatal(1,"malformed accepted");
        send(1,8'h42,6,1);if(accepted) $fatal(1,"CRC accepted");
        send(1,8'h42,6,0);send(1,4,0,0);send(1,8'h45,8,0);
        if(accepted!=3) $fatal(1,"valid commands rejected");
        send(1,8'h47,8,0);if(rejected!=4) $fatal(1,"short arc command accepted");
        send(1,8'h47,10,0);if(accepted!=4) $fatal(1,"arc command rejected");
        $display("PASS A741 command lengths, versions, CRC, STOP resynchronization");$finish;
    end
    initial begin #200000;$fatal(1,"watchdog");end
endmodule
