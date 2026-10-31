`timescale 1ns/1ps
`default_nettype none
// IPv4/UDP video sender. Each packet carries up to 1400 RGB565 bytes.
// Payload: 4-byte magic 'EV10', frame_id, packet_id, payload_bytes, pixels.
module a745_video_udp_tx #(parameter CLK_HZ=50000000,VIDEO_PORT=6104)(
 input wire clk,rst_n,phy_ready,input wire [17:0] fifo_data,input wire fifo_empty,
 output wire fifo_pop,output wire [7:0] data,output wire valid,last,input wire ready,
 output reg [31:0] dropped
);
 localparam PAYLOAD=1280;
 reg sending; reg [11:0] index; reg [10:0] payload_count; reg [31:0] frame_id; reg [15:0] packet_id; reg [18:0] frame_pixels;
 reg [15:0] ip_checksum;
 wire [15:0] ip_len=16'd28+16'd4+16'd8+PAYLOAD;
 wire [15:0] udp_len=16'd8+16'd4+16'd8+PAYLOAD;
 function [15:0] checksum(input [15:0] total);
  reg [19:0] s; reg [16:0] f; begin s=20'h385b9+total;f=s[15:0]+s[19:16];checksum=~(f[15:0]+f[16]); end
 endfunction
 wire take=fifo_pop;
 assign fifo_pop=sending && ready && index>=12'd55 && index<=12'd1453 && index[0];
 assign valid=sending;
 assign last=sending && index==12'd1333;
 assign data=index<42 ? (index==0||index==1||index==2||index==3||index==4||index==5 ? 8'hff :
   index==6 ? 8'h02 : index==11 ? 8'h02 : index==12 ? 8'h08 : index==14 ? 8'h45 :
   index==16 ? ip_len[15:8] : index==17 ? ip_len[7:0] : index==20 ? 8'h40 :
   index==22 ? 8'h40 : index==23 ? 8'h11 : index==24 ? ip_checksum[15:8] :
   index==25 ? ip_checksum[7:0] : index==26 ? 8'hc0 : index==27 ? 8'ha8 :
   index==29 ? 8'h02 : index==30||index==31||index==32||index==33 ? 8'hff :
   index==34 ? 8'h17 : index==35 ? 8'hd8 : index==36 ? VIDEO_PORT[15:8] :
   index==37 ? VIDEO_PORT[7:0] : index==38 ? udp_len[15:8] : index==39 ? udp_len[7:0] : 8'd0) :
   index==42 ? 8'h45 : index==43 ? 8'h56 : index==44 ? 8'h31 : index==45 ? 8'h30 :
   index==46 ? frame_id[7:0] : index==47 ? frame_id[15:8] : index==48 ? frame_id[23:16] :
   index==49 ? frame_id[31:24] : index==50 ? packet_id[7:0] : index==51 ? packet_id[15:8] :
   index==52 ? PAYLOAD[7:0] : index==53 ? PAYLOAD[10:8] : fifo_data[index[0] ? 15:0];
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin sending<=0;index<=0;payload_count<=0;frame_id<=0;packet_id<=0;frame_pixels<=0;ip_checksum<=0;dropped<=0;end
  else begin
   if(!sending && phy_ready && !fifo_empty) begin sending<=1;index<=0;payload_count<=0;ip_checksum<=checksum(16'd1432);end
   if(sending && ready) begin
    if(index>=12'd54 && index<12'd1334 && fifo_empty) begin sending<=0;dropped<=dropped+1'b1;end
    else if(index>=12'd55 && index<=12'd1333 && index[0]) begin
     payload_count<=payload_count+1'b1;
     if(frame_pixels==19'd307199) begin frame_pixels<=0;frame_id<=frame_id+1'b1;packet_id<=0;end
     else frame_pixels<=frame_pixels+1'b1;
    end
    if(last) begin sending<=0;packet_id<=packet_id+1'b1;end else index<=index+1'b1;
   end
  end
endmodule
`default_nettype wire
