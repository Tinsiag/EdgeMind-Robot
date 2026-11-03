`timescale 1ns/1ps
module task_telemetry_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,ms_tick=0,phy_ready=0,lidar_valid=0;
 reg [895:0] snapshot=0;reg [255:0] fusion_snapshot=0;
 reg [511:0] task_snapshot=0;reg [375:0] lidar_packet=0;
 reg [31:0] lidar_seq=0,lidar_time=0;
 wire [7:0] data;wire valid,last;wire [31:0] dropped;reg ready=0;
 a745_udp_tx #(.TASK_ENABLE(1)) dut(.*);
 integer cycle=0,frames=0,index=0,i,fd;reg stalled=0;reg [7:0] held;reg held_last;
 always @(negedge clk)begin cycle=cycle+1;ready=cycle%7!=0;end
 always @(posedge clk)if(rst_n)begin
  if(stalled && (!valid || data!==held || last!==held_last))$fatal(1,"task AXI changed during stall");
  stalled=valid&&!ready;held=data;held_last=last;
  if(valid&&ready)begin
   $fwrite(fd,"%02x ",data);
   if(frames==2 && index>=42 && data!==task_snapshot[(index-42)*8+:8])$fatal(1,"task payload corruption %0d",index);
   if(last)begin
    if(frames==2 && index!=105)$fatal(1,"task packet length");
    $fwrite(fd,"\n");frames=frames+1;index=0;
   end else index=index+1;
  end
 end
 initial begin
  fd=$fopen(".local/tests/task-telemetry.hex","w");
  for(i=0;i<64;i=i+1)task_snapshot[i*8+:8]=i;
  task_snapshot[31:0]=32'h31544d45;task_snapshot[63:32]={16'd64,16'd1};
  task_snapshot[95:64]=74513;task_snapshot[191:160]=32'h12345678;
  repeat(5)@(negedge clk);rst_n=1;
  repeat(100)begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end
  if(valid)$fatal(1,"task sent before PHY ready");phy_ready=1;
  wait(frames==3);repeat(5)@(negedge clk);$fclose(fd);
  $display("PASS enabled EMT1 telemetry framing, snapshot, PHY gate and AXI stalls");$finish;
 end
 initial begin #1000000;$fatal(1,"task telemetry timeout");end
endmodule
