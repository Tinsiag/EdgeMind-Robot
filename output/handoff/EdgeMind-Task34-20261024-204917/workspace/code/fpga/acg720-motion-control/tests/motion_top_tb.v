`timescale 1ns/1ps
module motion_top_tb;
    reg clk=0,stop_n=0,uart_rx=1,left_enc_a=0,left_enc_b=0,right_enc_a=0,right_enc_b=0;
    wire uart_tx,left_in1,left_in2,right_in1,right_in2; wire [7:0] led;
    always #10 clk=~clk;
    motion_top #(.CLK_HZ(5000000),.PWM_HZ(5000)) dut(.*);
    task uart_byte(input [7:0] d); integer i; begin uart_rx=0; repeat(43) @(posedge clk); for(i=0;i<8;i=i+1) begin uart_rx=d[i]; repeat(43) @(posedge clk); end uart_rx=1; repeat(43) @(posedge clk); end endtask
    function [15:0] crc16; input [15:0] c; input [7:0] d; integer k; reg [15:0] x; begin x=c; for(k=0;k<8;k=k+1)x=(x[15]^d[7-k])?((x<<1)^16'h1021):(x<<1);crc16=x;end endfunction
    reg [15:0] crc; integer i;
    task send_frame(input [7:0] typ); begin crc=16'hffff; uart_byte(8'hAA);uart_byte(8'h55); for(i=0;i<6;i=i+1) begin case(i) 0: begin uart_byte(1);crc=crc16(crc,1);end 1:begin uart_byte(typ);crc=crc16(crc,typ);end 2:begin uart_byte(0);crc=crc16(crc,0);end 3:begin uart_byte(1);crc=crc16(crc,1);end 4:begin uart_byte(0);crc=crc16(crc,0);end 5:begin uart_byte(0);crc=crc16(crc,0);end endcase end uart_byte(crc[7:0]);uart_byte(crc[15:8]); end endtask
    initial begin #100; stop_n=1; repeat(1000) @(posedge clk); send_frame(8'h02); repeat(1000) @(posedge clk); if(led[1]!==0) $display("ARM correctly blocked until parameters"); send_frame(8'h04); repeat(100); $display("PASS top safety smoke"); $finish; end
endmodule
