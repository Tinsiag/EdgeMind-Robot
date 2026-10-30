`timescale 1ns/1ps
`default_nettype none
// Ethernet/IPv4/UDP broadcast telemetry. No RX, ARP cache, command parser,
// host session, configuration writes or network-controlled motion exists.
// IPv4 permits a zero UDP checksum. The MAC adds preamble/padding/FCS.
module a745_udp_tx #(parameter CLK_HZ=50000000)(
 input wire clk,rst_n,ms_tick,phy_ready,
 input wire [895:0] snapshot,input wire [255:0] fusion_snapshot,
 input wire lidar_valid,input wire [375:0] lidar_packet,input wire [31:0] lidar_seq,lidar_time,
 output wire [7:0] data,output wire valid,last,input wire ready,
 output reg [31:0] dropped
);
 reg sending,radar_pending,status_pending,fusion_pending;
 reg [6:0] status_timer;reg [7:0] index,length;
 reg [895:0] bytes;reg [511:0] radar;
 reg [15:0] ip_checksum;
 wire [15:0] ip_length={8'd0,length}+16'd28;
 wire [15:0] udp_length={8'd0,length}+16'd8;
 // Sum of fixed header words: 4500,0000,4000,4011,c0a8,0002,ffff,ffff.
 function [15:0] header_checksum(input [15:0] total);
  reg [19:0] sum;reg [16:0] folded;
  begin sum=20'h385b9+total;folded=sum[15:0]+sum[19:16];header_checksum=~(folded[15:0]+folded[16]);end
 endfunction
 reg [7:0] header;
 always @* begin
  header=0;
  case(index)
   0,1,2,3,4,5:header=8'hff;
   6:header=2;7,8,9,10:header=0;11:header=2;
   12:header=8'h08;13:header=0;
   14:header=8'h45;15:header=0;16:header=ip_length[15:8];17:header=ip_length[7:0];
   18,19:header=0;20:header=8'h40;21:header=0;22:header=8'h40;23:header=8'h11;
   24:header=ip_checksum[15:8];25:header=ip_checksum[7:0];
   26:header=192;27:header=168;28:header=0;29:header=2;
   30,31,32,33:header=255;
   34:header=8'h17;35:header=8'hd7;36:header=8'h17;37:header=8'hd7;
   38:header=udp_length[15:8];39:header=udp_length[7:0];40,41:header=0;
  endcase
 end
 assign data=index<42 ? header:bytes[7:0];
 assign valid=sending;
 assign last=sending && index==length+8'd41;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin sending<=0;radar_pending<=0;status_pending<=0;fusion_pending<=0;
   status_timer<=0;index<=0;length<=0;bytes<=0;radar<=0;ip_checksum<=0;dropped<=0;end
  else begin
   if(ms_tick) begin
    if(status_timer==99) begin status_timer<=0;status_pending<=1;fusion_pending<=1;end
    else status_timer<=status_timer+1'b1;
   end
   if(lidar_valid) begin
    if(radar_pending) dropped<=dropped+1'b1;
    radar<={8'd0,lidar_packet,lidar_time,lidar_seq,16'd64,16'd1,32'h314c4d45};radar_pending<=1;
   end
   if(!sending && phy_ready) begin
    index<=0;
    if(status_pending) begin
     bytes<=snapshot;length<=112;ip_checksum<=header_checksum(140);status_pending<=0;sending<=1;
    end else if(fusion_pending) begin
     bytes<={512'd0,fusion_snapshot,snapshot[127:64],16'd48,16'd1,32'h31464d45};
     length<=48;ip_checksum<=header_checksum(76);fusion_pending<=0;sending<=1;
    end else if(radar_pending) begin
     bytes<={384'd0,radar};length<=64;ip_checksum<=header_checksum(92);radar_pending<=lidar_valid;sending<=1;
    end
   end
   if(sending && ready) begin
    if(index>=42) bytes<=bytes>>8;
    if(last) sending<=0;else index<=index+1'b1;
   end
  end
endmodule
`default_nettype wire
