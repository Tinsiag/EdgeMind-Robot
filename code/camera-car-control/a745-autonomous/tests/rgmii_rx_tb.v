`timescale 1ns/1ps
// Exercise actual Gowin DDR cells -> GMII MAC/FCS -> asynchronous frame FIFO -> ED10.
module rgmii_rx_tb;
 GSR GSR(.GSRI(1'b1));
 reg rclk=0,lclk=0,pclk=0,rst=1;always #4 rclk=~rclk;always #4.1 lclk=~lclk;always #10 pclk=~pclk;
 reg [3:0] rdata=0;reg rctl=0;wire [7:0] gmii_data;wire gmii_valid,gmii_error;
 a745_rgmii_rx pads(.clk(rclk),.data(rdata),.ctl(rctl),.*);
 wire [7:0] data;wire valid,last,user,ready,update;wire [771:0] detections;wire [7:0] accepted;
 wire [7:0] parsed_data;wire parsed_valid,parsed_last,parsed_user,parsed_ready;
 eth_mac_1g_fifo mac(.rx_clk(rclk),.rx_rst(rst),.tx_clk(lclk),.tx_rst(rst),
  .logic_clk(lclk),.logic_rst(rst),.tx_axis_tdata(8'd0),.tx_axis_tkeep(1'b1),
  .tx_axis_tvalid(1'b0),.tx_axis_tlast(1'b0),.tx_axis_tuser(1'b0),
  .rx_axis_tdata(data),.rx_axis_tvalid(valid),.rx_axis_tlast(last),.rx_axis_tuser(user),.rx_axis_tready(ready),
  .gmii_rxd(gmii_data),.gmii_rx_dv(gmii_valid),.gmii_rx_er(gmii_error),
  .rx_clk_enable(1'b1),.tx_clk_enable(1'b1),.rx_mii_select(1'b0),.tx_mii_select(1'b0),
  .cfg_ifg(8'd12),.cfg_tx_enable(1'b0),.cfg_rx_enable(1'b1));
 axis_async_fifo #(.DEPTH(512),.DATA_WIDTH(8),.KEEP_ENABLE(0),.FRAME_FIFO(1),.DROP_BAD_FRAME(1)) parser_fifo(
  .s_clk(lclk),.s_rst(rst),.s_axis_tdata(data),.s_axis_tkeep(1'b1),.s_axis_tvalid(valid),.s_axis_tready(ready),
  .s_axis_tlast(last),.s_axis_tuser(user),.s_axis_tid(8'd0),.s_axis_tdest(8'd0),
  .m_clk(pclk),.m_rst(rst),.m_axis_tdata(parsed_data),.m_axis_tvalid(parsed_valid),.m_axis_tready(parsed_ready),
  .m_axis_tlast(parsed_last),.m_axis_tuser(parsed_user),.s_pause_req(1'b0),.m_pause_req(1'b0));
 a745_detection_rx dut(.clk(pclk),.rst_n(!rst),.data(parsed_data),.valid(parsed_valid&&parsed_ready),
  .last(parsed_last),.user(parsed_user),.ready(parsed_ready),.update_ready(1'b1),.update(update),.detections(detections),.accepted(accepted));
 reg [7:0] packet[0:511];integer n,i,j,s;reg [31:0] crc;reg [7:0] b;
 task emit(input [7:0] value,input dv,input er);
 begin
  // Data valid for both DDR edges; IDDR aligns their samples to one byte.
  @(negedge rclk);#1;rdata=value[3:0];rctl=dv;
  @(posedge rclk);#1;rdata=value[7:4];rctl=dv^er;
 end endtask
 task send(input bad_fcs,input error_ctl);
 begin
  for(i=0;i<7;i=i+1)emit(8'h55,1,0);emit(8'hd5,1,0);
  crc=32'hffffffff;
  for(i=0;i<n;i=i+1)begin
   b=packet[i];for(j=0;j<8;j=j+1)crc=(crc>>1)^((crc[0]^b[j])?32'hedb88320:0);
   emit(b,1,error_ctl && i==20);
  end
  crc=~crc;if(bad_fcs)crc=crc^1;
  for(i=0;i<4;i=i+1)emit(crc>>(8*i),1,0);
  emit(0,0,0);repeat(600)@(negedge rclk);
 end endtask
 initial begin
  for(i=0;i<512;i=i+1)packet[i]=0;n=70;
  packet[0]=2;packet[5]=2;packet[6]='h48;packet[7]='hda;packet[8]='h35;packet[9]='h60;packet[11]='h99;
  packet[12]=8;packet[14]='h45;packet[17]=56;packet[22]=64;packet[23]=17;
  packet[26]=192;packet[27]=168;packet[29]=3;packet[30]=192;packet[31]=168;packet[33]=2;
  packet[34]='h17;packet[35]='hd9;packet[36]='h17;packet[37]='hd9;packet[39]=36;
  packet[42]="E";packet[43]="D";packet[44]="1";packet[45]="0";packet[46]=1;
  packet[50]=1;packet[52]='h80;packet[53]=2;packet[54]='he0;packet[55]=1;
  packet[58]=10;packet[60]=20;packet[62]=100;packet[64]=200;packet[67]=200;
  s=0;for(i=14;i<34;i=i+2)s=s+(packet[i]*256+packet[i+1]);
  s=(s&65535)+(s>>16);s=(~s)&65535;packet[24]=s>>8;packet[25]=s;
  s='h18166+36;for(i=34;i<70;i=i+2)s=s+(packet[i]*256+packet[i+1]);
  s=(s&65535)+(s>>16);s=(~s)&65535;packet[40]=s>>8;packet[41]=s;
  repeat(20)@(negedge rclk);rst=0;repeat(20)@(negedge rclk);
  send(1,0);if(accepted!=0)$fatal(1,"bad FCS published");
  send(0,1);if(accepted!=0)$fatal(1,"RX_ER published");
  send(0,0);if(accepted!=1 || detections[4+:16]!=10)$fatal(1,"RGMII MAC detection chain count=%d",accepted);
  $display("PASS Gowin IDDR RGMII -> MAC FCS/error rejection -> async FIFO -> detection parser");$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
