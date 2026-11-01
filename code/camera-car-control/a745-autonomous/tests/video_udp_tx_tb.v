`timescale 1ns/1ps
`default_nettype none
// End-to-end: a741_tft800_panel timing -> a745_video_capture_tx ->
// async_fifo -> a745_video_udp_tx with random back-pressure. Checks every
// packet: length 1334, framing, independent IPv4 checksum, EV10 header,
// line order 0..479 and pixel values {y,x} of the 640-pixel window.
module video_udp_tx_tb;
 reg dclk=0,clk=0,rst_n=0;
 always #15.151 dclk=~dclk;   // 33 MHz display
 always #10 clk=~clk;         // 50 MHz control
 wire active,pixel_request,frame_blank; wire [10:0] x,y;
 wire [15:0] pixel={y[7:0],x[7:0]};
 a741_tft800_panel #(.BACKLIGHT_FRAMES(0)) panel(.clk(dclk),.rst_n(rst_n),.rgb(16'd0),
  .pixel_request(pixel_request),.frame_blank(frame_blank),.active(active),.x(x),.y(y),
  .tft_clk(),.tft_de(),.tft_hsync(),.tft_vsync(),.tft_bl(),.tft_rgb());
 wire [27:0] tok,rtok; wire tv,empty,pop; wire [11:0] level,wlevel; wire [31:0] skipped;
 a745_video_capture_tx #(.FRAME_DIV(2),.DEPTH(2048),.LEVEL_BITS(12)) cap(.clk(dclk),.rst_n(rst_n),.active(active),.pixel_valid(1'b1),
  .x(x),.y(y),.pixel(pixel),.wr_level(wlevel),.token(tok),.valid(tv),.skipped_lines(skipped));
 async_fifo #(.WIDTH(28),.ADDR_BITS(11),.LEVELS(1)) fifo(.wr_clk(dclk),.wr_rst_n(rst_n),.wr_en(tv),.wr_data(tok),.full(),.wr_level(wlevel),
  .rd_clk(clk),.rd_rst_n(rst_n),.rd_en(pop),.rd_data(rtok),.empty(empty),.rd_level(level));
 reg ready=0; wire [7:0] data; wire valid,last; wire [31:0] frames,resync;
 a745_video_udp_tx #(.LINE_PIXELS(640),.LEVEL_BITS(12)) dut(.clk(clk),.rst_n(rst_n),.phy_ready(1'b1),
  .fifo_data(rtok),.fifo_empty(empty),.fifo_level(level),.fifo_pop(pop),.data(data),.valid(valid),.last(last),
  .ready(ready),.frames(frames),.resync(resync));
 // Default: realistic MAC drain (~94% ready) must deliver complete frames.
 // +STRESS: 75% ready forces whole-line skips; alignment must still hold.
 integer stress=0;
 initial if($test$plusargs("STRESS")) stress=1;
 always @(posedge clk) ready<=stress ? (($random & 3)!=0):(($random & 15)!=0);

 reg [7:0] pkt[0:2047]; integer n=0,packets=0,errors=0,prev_line=-1,last_frame=-1,lines_done=0;
 integer i,s,fid,ln,sz,px,want,full_frames=0,frames_seen=0;
 task fail(input [8*64-1:0] msg); begin errors=errors+1; if(errors<10) $display("ERR pkt%0d: %0s",packets,msg); end endtask
 always @(posedge clk) if(valid && ready) begin
  pkt[n]=data; n=n+1;
  if(last) begin
   if(n!=1334) fail("length");
   if(pkt[12]!=8'h08||pkt[13]!=8'h00||pkt[14]!=8'h45||pkt[23]!=8'h11) fail("eth/ip type");
   if({pkt[16],pkt[17]}!=16'd1320||{pkt[38],pkt[39]}!=16'd1300) fail("ip/udp length");
   if({pkt[36],pkt[37]}!=16'd6104) fail("dst port");
   s=0; for(i=14;i<34;i=i+2) s=s+{pkt[i],pkt[i+1]};
   s=(s&16'hffff)+(s>>16); s=(s&16'hffff)+(s>>16);
   if(s!=16'hffff) fail("ip checksum");
   if(pkt[42]!="E"||pkt[43]!="V"||pkt[44]!="1"||pkt[45]!="0") fail("magic");
   fid={pkt[49],pkt[48],pkt[47],pkt[46]}; ln={pkt[51],pkt[50]}; sz={pkt[53],pkt[52]};
   if(sz!=1280) fail("payload size");
   if(ln>=480) fail("line range");
   if(fid!=last_frame) begin
    if(last_frame>=0) begin frames_seen=frames_seen+1; if(lines_done==480) full_frames=full_frames+1; end
    if(last_frame>=0 && fid!=last_frame+1) fail("frame id step");
    last_frame=fid; prev_line=-1; lines_done=0;
   end
   if(ln<=prev_line) fail("line order");
   prev_line=ln; lines_done=lines_done+1;
   for(i=0;i<640;i=i+1) begin
    px={pkt[55+2*i],pkt[54+2*i]}; want=((ln&255)<<8)|((80+i)&255);
    if(px!=want) begin if(errors<3) $display("ln=%0d i=%0d px=%h want=%h fid=%0d",ln,i,px,want,fid); fail("pixel"); i=640; end
   end
   packets=packets+1; n=0;
  end
 end
 initial begin
  #200 rst_n=1;
  // 6 display frames -> 3 forwarded frames (FRAME_DIV=2)
  #101_000_000;
  if(last_frame>=0) begin frames_seen=frames_seen+1; if(lines_done==480) full_frames=full_frames+1; end
  $display("stress=%0d packets=%0d frames_seen=%0d full_frames=%0d sender_frames=%0d resync=%0d skipped_lines=%0d errors=%0d",
   stress,packets,frames_seen,full_frames,frames,resync,skipped,errors);
  if(errors==0 && frames_seen>=3 && resync==0 && (stress ? skipped>0 && packets>0 : full_frames>=3 && skipped==0))
   $display("PASS video_udp_tx_tb"); else $display("FAIL video_udp_tx_tb");
  $finish;
 end
endmodule
`default_nettype wire
