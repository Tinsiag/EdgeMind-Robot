`timescale 1ns/1ps
module camera_boot_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,present=1,bad_id=0;wire camera_reset_n,ready,error;wire [47:0] diagnostic;
 wire scl;tri1 sda;
 a745_camera_boot #(.CLK_HZ(1000000),.POWER_MS(1),.RELEASE_MS(25),.MAX_ATTEMPTS(3)) dut(.*);
 camera_model camera(.scl(scl),.sda(sda),.reset_n(camera_reset_n),.present(present),.bad_id(bad_id));
 task reset;begin @(negedge clk);rst_n=0;repeat(5) @(negedge clk);rst_n=1;end endtask
 initial begin
  reset;wait(ready || error);
  if(!ready || error || camera.regs[16'h3809]!=32 || camera.regs[16'h380b]!=224 || camera.writes!=254)
   $fatal(1,"camera cold boot failed ready=%b error=%b diag=%h writes=%0d",ready,error,diagnostic,camera.writes);
  reset;wait(ready || error);if(!ready) $fatal(1,"powered sensor FPGA reload failed %h",diagnostic);
  present=0;reset;wait(error);if(ready || diagnostic[47:40]!=1) $fatal(1,"NACK not bounded/reported %h",diagnostic);
  present=1;bad_id=1;reset;wait(error);if(ready || diagnostic[47:40]!=4 || diagnostic[31:16]!=16'h300b) $fatal(1,"bad chip ID accepted %h",diagnostic);
  bad_id=0;reset;wait(ready || error);if(!ready) $fatal(1,"recovery failed");
  $display("PASS actual chapter45 I2C waveform + RGB ROM: cold boot/reload, 254 writes, 17 critical reads, physical-reset retries, missing sensor/bad-ID rejection");$finish;
 end
 initial begin #30000000;$fatal(1,"camera watchdog %h",diagnostic);end
endmodule

// Behavioral SCCB register device, not a mock of the controller. It samples
// actual SCL/SDA START, bytes, ACK and STOP/START reads on the external wires.
module camera_model(input scl,reset_n,present,bad_id,inout sda);
 reg drive=0;assign sda=drive ? 1'b0:1'bz;
 reg [7:0] regs[0:65535];reg [15:0] pointer;reg [7:0] dev,hi,lo,value;integer i,writes=0;
 always @(negedge reset_n) begin
  for(i=0;i<65536;i=i+1) regs[i]=0;
  regs[16'h300a]=8'h56;regs[16'h300b]=8'h40;writes=0;
 end
 task receive(output [7:0] b,input ack);
  integer k;
  begin
   for(k=7;k>=0;k=k-1) begin @(posedge scl);b[k]=sda;end
   @(negedge scl);drive=ack && present && reset_n;
   @(posedge scl);@(negedge scl);drive=0;
  end
 endtask
 task send(input [7:0] b);
  integer k;
  begin for(k=7;k>=0;k=k-1) begin drive=!b[k];@(posedge scl);@(negedge scl);end
   drive=0;@(posedge scl);@(negedge scl);
  end
 endtask
 task stopped;
  begin : stop_wait
   forever begin @(posedge sda);if(scl===1'b1) disable stop_wait;end
  end
 endtask
 initial forever begin : transaction
  drive=0;
  begin : start_wait
   forever begin @(negedge sda);if(scl===1'b1) disable start_wait;end
  end
  receive(dev,1);
  if(dev==8'h78 && present && reset_n) begin
   receive(hi,1);receive(lo,1);pointer={hi,lo};
   fork : data_or_stop
    begin receive(value,1);regs[pointer]=value;writes=writes+1;end
    stopped;
   join_any
   disable data_or_stop;
  end else if(dev==8'h79 && present && reset_n) send(regs[pointer] ^ ((bad_id && pointer==16'h300b) ? 8'h01:8'h00));
 end
endmodule
