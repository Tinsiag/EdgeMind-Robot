`timescale 1ns/1ps
`default_nettype none
// One SCCB owner. Every attempt resets the physical sensor and the bus engine.
// The byte/bit engine is the unchanged ACG720 chapter45 implementation; unlike
// the earlier controller it uses the manufacturer's STOP/START register reads.
module a745_camera_boot #(parameter CLK_HZ=50000000,MAX_ATTEMPTS=4,
    POWER_MS=100,RESET_MS=2,RELEASE_MS=25)(
 input wire clk,rst_n,output wire camera_reset_n,inout wire scl,sda,
 output reg ready,error,output wire [47:0] diagnostic
);
 localparam POWER=0,RESET=1,RELEASE=2,ROM1=3,ROM2=4,WRITE=5,WAIT_WRITE=6,
            SOFT_DELAY=7,READ=8,WAIT_READ=9,SETTLE=10,DONE=11,FAILED=12;
 reg [3:0] state; reg [31:0] timer; reg [2:0] attempt;
 reg [7:0] index,check_index,code,last_value,expected;
 reg [15:0] address;reg [7:0] data;reg wr,rd;
 wire done,nack;wire [7:0] value;wire [23:0] rom;
 wire bus_reset_n=rst_n && state!=POWER && state!=RESET && state!=FAILED;
 assign camera_reset_n=rst_n && state!=POWER && state!=RESET && state!=FAILED;
 assign diagnostic={code,{1'b0,state,attempt},address,expected,last_value};
 ov5640_init_table_rgb #(.IMAGE_WIDTH(800),.IMAGE_HEIGHT(480)) table_rgb(.clk(clk),.addr(index),.q(rom));
 i2c_control #(.SYS_CLOCK(CLK_HZ),.SCL_CLOCK(100000)) bus(
  .Clk(clk),.Rst_n(bus_reset_n),.wrreg_req(wr),.rdreg_req(rd),.addr(address),
  .addr_mode(1'b1),.wrdata(data),.rddata(value),.device_id(8'h78),.RW_Done(done),
  .ack(nack),.dly_cnt_max(32'd0),.i2c_sclk(scl),.i2c_sdat(sda));
 reg [15:0] check_address;reg [7:0] check_value,check_mask;
 always @* begin
  check_address=16'h300a;check_value=8'h56;check_mask=8'hff;
  case(check_index)
   1:begin check_address=16'h300b;check_value=8'h40;end
   2:begin check_address=16'h3008;check_value=8'h02;check_mask=8'hc2;end
   3:begin check_address=16'h3034;check_value=8'h1a;end
   4:begin check_address=16'h3035;check_value=8'h21;end
   5:begin check_address=16'h3036;check_value=8'h69;end
   6:begin check_address=16'h3037;check_value=8'h13;end
   7:begin check_address=16'h3808;check_value=8'h03;end
   8:begin check_address=16'h3809;check_value=8'h20;end
   9:begin check_address=16'h380a;check_value=8'h01;end
   10:begin check_address=16'h380b;check_value=8'he0;end
   11:begin check_address=16'h4300;check_value=8'h61;end
   12:begin check_address=16'h501f;check_value=8'h01;end
   13:begin check_address=16'h5001;check_value=8'ha3;end
   14:begin check_address=16'h503d;check_value=8'h00;end
   15:begin check_address=16'h4740;check_value=8'h20;end
   16:begin check_address=16'h4741;check_value=8'h00;end
  endcase
 end
 task retry;
  input [7:0] why;
  begin
   code<=why;ready<=0;timer<=0;wr<=0;rd<=0;
   if(attempt<MAX_ATTEMPTS) begin attempt<=attempt+1'b1;state<=RESET;end
   else begin error<=1;state<=FAILED;end
  end
 endtask
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   state<=POWER;timer<=0;attempt<=1;index<=0;check_index<=0;code<=0;
   address<=0;data<=0;expected<=0;last_value<=0;wr<=0;rd<=0;ready<=0;error<=0;
  end else begin
   wr<=0;rd<=0;
   if(timer<CLK_HZ) timer<=timer+1'b1;
   // Transaction watchdog also recovers a stuck bus/engine; it never hangs
   // forever with camera_ready=0 and no visible explanation.
   if((state==WAIT_WRITE || state==WAIT_READ) && timer>=CLK_HZ/20) retry(8'h03);
   else case(state)
    POWER:if(timer>=CLK_HZ/1000*POWER_MS-1) begin state<=RESET;timer<=0;end
    RESET:if(timer>=CLK_HZ/1000*RESET_MS-1) begin state<=RELEASE;timer<=0;index<=0;check_index<=0;end
    RELEASE:if(timer>=CLK_HZ/1000*RELEASE_MS-1) begin state<=ROM1;timer<=0;end
    ROM1:state<=ROM2;
    ROM2:begin address<=rom[23:8];data<=rom[7:0];state<=WRITE;end
    WRITE:begin wr<=1;timer<=0;state<=WAIT_WRITE;end
    WAIT_WRITE:if(done) begin
     if(nack) retry(8'h01);
     else if(index==1) begin state<=SOFT_DELAY;timer<=0;end
     else if(index==253) begin check_index<=0;state<=READ;end
     else begin index<=index+1'b1;state<=ROM1;end
    end
    SOFT_DELAY:if(timer>=CLK_HZ/200-1) begin index<=2;state<=ROM1;end
    READ:begin address<=check_address;expected<=check_value;rd<=1;timer<=0;state<=WAIT_READ;end
    WAIT_READ:if(done) begin
     last_value<=value;
     if(nack) retry(8'h02);
     else if((value & check_mask)!=(expected & check_mask)) retry(8'h04);
     else if(check_index==16) begin timer<=0;state<=SETTLE;end
     else begin check_index<=check_index+1'b1;state<=READ;end
    end
    SETTLE:if(timer>=CLK_HZ/20-1) begin ready<=1;error<=0;code<=0;state<=DONE;end
    DONE:begin end
    FAILED:begin end
    default:retry(8'hff);
   endcase
  end
endmodule
`default_nettype wire
