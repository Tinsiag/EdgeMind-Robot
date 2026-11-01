`timescale 1ns/1ps
`default_nettype none
// IPv4/UDP video sender: one 640-pixel RGB565 line per packet.
// Ethernet broadcast, 192.168.0.2:6104 -> 192.168.0.3:VIDEO_PORT.
// EV10 header (little endian): 'EV10', frame_id u32, line u16, bytes u16.
// Input tokens {sof,sol,y[9:0],rgb565} come from an FWFT FIFO whose read-side
// occupancy is fifo_level. A packet starts only when a complete line is
// already buffered, so the payload can never underflow mid-frame and every
// packet is closed with tlast. Tokens that do not begin a line are discarded
// while idle to resynchronise after any upstream loss. The header line
// number is the real display y, and a new frame_id starts on sof or when y
// does not increase, so a skipped line can never shift the image.
module a745_video_udp_tx #(parameter VIDEO_PORT=6104,LINE_PIXELS=640,LEVEL_BITS=14)(
 input wire clk,rst_n,phy_ready,input wire [27:0] fifo_data,input wire fifo_empty,
 input wire [LEVEL_BITS-1:0] fifo_level,
 output wire fifo_pop,output wire [7:0] data,output wire valid,last,input wire ready,
 output reg [31:0] frames,output reg [31:0] resync
);
 localparam PAYLOAD=LINE_PIXELS*2;
 localparam HDR=54;                      // 14 eth + 20 ip + 8 udp + 12 EV10
 localparam LAST=HDR+PAYLOAD-1;
 localparam [15:0] UDP_LEN=8+12+PAYLOAD;
 localparam [15:0] IP_LEN=20+UDP_LEN;
 localparam [31:0] CS_SUM=32'h4500+IP_LEN+32'h4000+32'h4011+32'hc0a8+32'h0002+32'hc0a8+32'h0003;
 localparam [31:0] CS_F1=CS_SUM[15:0]+CS_SUM[31:16];
 localparam [31:0] CS_F2=CS_F1[15:0]+CS_F1[31:16];
 localparam [15:0] IP_CSUM=~CS_F2[15:0];
 localparam [15:0] SRC_PORT=16'd6104;
 localparam [15:0] DST_PORT=VIDEO_PORT;
 localparam [15:0] PAYLOAD16=PAYLOAD;

 reg sending; reg [11:0] index; reg [31:0] frame_id; reg [15:0] line;
 wire head_sol=!fifo_empty && fifo_data[26];
 wire [9:0] head_y=fifo_data[25:16];
 wire start=!sending && phy_ready && head_sol && fifo_level>=LINE_PIXELS;
 wire discard=!sending && !fifo_empty && !fifo_data[26];
 wire payload_pop=sending && ready && index>=HDR+1 && index[0];
 assign fifo_pop=discard || payload_pop;
 assign valid=sending;
 assign last=sending && index==LAST;

 reg [7:0] hdr;
 always @* begin
  case(index[5:0])
   0,1,2,3,4,5: hdr=8'hff;
   6: hdr=8'h02; 7,8,9,10: hdr=8'h00; 11: hdr=8'h02;
   12: hdr=8'h08; 13: hdr=8'h00;
   14: hdr=8'h45; 15: hdr=8'h00; 16: hdr=IP_LEN[15:8]; 17: hdr=IP_LEN[7:0];
   18,19: hdr=8'h00; 20: hdr=8'h40; 21: hdr=8'h00; 22: hdr=8'h40; 23: hdr=8'h11;
   24: hdr=IP_CSUM[15:8]; 25: hdr=IP_CSUM[7:0];
   26: hdr=8'hc0; 27: hdr=8'ha8; 28: hdr=8'h00; 29: hdr=8'h02;
   30: hdr=8'hc0; 31: hdr=8'ha8; 32: hdr=8'h00; 33: hdr=8'h03;
   34: hdr=SRC_PORT[15:8]; 35: hdr=SRC_PORT[7:0]; 36: hdr=DST_PORT[15:8]; 37: hdr=DST_PORT[7:0];
   38: hdr=UDP_LEN[15:8]; 39: hdr=UDP_LEN[7:0]; 40,41: hdr=8'h00;   // UDP checksum unused
   42: hdr=8'h45; 43: hdr=8'h56; 44: hdr=8'h31; 45: hdr=8'h30;      // 'EV10'
   46: hdr=frame_id[7:0]; 47: hdr=frame_id[15:8]; 48: hdr=frame_id[23:16]; 49: hdr=frame_id[31:24];
   50: hdr=line[7:0]; 51: hdr=line[15:8];
   52: hdr=PAYLOAD16[7:0]; 53: hdr=PAYLOAD16[15:8];
   default: hdr=8'h00;
  endcase
 end
 // FWFT: low byte on even payload index, high byte then pop on odd index.
 assign data=index<HDR ? hdr:(index[0] ? fifo_data[15:8]:fifo_data[7:0]);

 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin sending<=0;index<=0;frame_id<=0;line<=0;frames<=0;resync<=0;end
  else begin
   if(discard) resync<=resync+1'b1;
   if(start) begin
    sending<=1;index<=0;
    line<={6'd0,head_y};
    if(fifo_data[27] || head_y<=line[9:0]) begin frame_id<=frame_id+1'b1;frames<=frames+1'b1;end
   end
   if(sending && ready) begin
    if(last) begin sending<=0;index<=0;end else index<=index+1'b1;
   end
  end
endmodule
`default_nettype wire
