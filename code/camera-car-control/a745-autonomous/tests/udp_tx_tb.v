`timescale 1ns/1ps
module udp_tx_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,phy_ready=0,lidar_valid=0;reg [895:0] snapshot=0;reg [255:0] fusion_snapshot=0;
 reg [375:0] lidar_packet=0;reg [31:0] lidar_seq=0,lidar_time=0;
 wire [7:0] data;wire valid,last;wire [31:0] dropped;reg ready=0;
 a745_udp_tx dut(.*);
 integer cycle=0,count=0,frames=0,fd=0;
 reg stalled=0;reg [7:0] held;reg held_last;
 always @(negedge clk) begin cycle=cycle+1;ready=cycle%5!=0;end
 always @(posedge clk) if(rst_n) begin
  if(stalled && (!valid || data!==held || last!==held_last)) $fatal(1,"AXI changed under backpressure");
  stalled=valid && !ready;held=data;held_last=last;
  if(valid && ready) begin $fwrite(fd,"%02x ",data);count=count+1;if(last) begin $fwrite(fd,"\n");frames=frames+1;end end
 end
 integer i;
 initial begin
  fd=$fopen(".local/tests/udp-frames.hex","w");snapshot[31:0]=32'h31534d45;snapshot[47:32]=1;snapshot[63:48]=112;
  for(i=8;i<112;i=i+1)snapshot[i*8+:8]=i;
  repeat(5) @(negedge clk);rst_n=1;
  repeat(100) begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end
  if(valid) $fatal(1,"sent before PHY ready");
  phy_ready=1;wait(frames==2);
  @(negedge clk);lidar_valid=1;lidar_seq=32'h12345678;lidar_time=32'h11223344;
  @(negedge clk);lidar_valid=0;wait(frames==3);
  repeat(10) @(negedge clk);$fclose(fd);
  $display("PASS TX-only status/fusion/radar frames, PHY wait and AXI backpressure; packet bytes exported for independent checksum validation");$finish;
 end
 initial begin #1000000;$fatal(1,"UDP watchdog");end
endmodule
