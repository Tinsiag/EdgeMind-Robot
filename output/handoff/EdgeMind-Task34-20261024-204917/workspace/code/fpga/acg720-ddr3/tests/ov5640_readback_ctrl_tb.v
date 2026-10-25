`timescale 1ns/1ps
module ov5640_readback_ctrl_tb;
    reg clk=0,rst_n=0,enable=0;
    always #10 clk=~clk;
    wire init_busy,init_done,init_error;
    wire [7:0] last_read_id,table_index;
    tri1 sccb_sda,sccb_scl;
    ov5640_ctrl #(.IMAGE_WIDTH(800),.IMAGE_HEIGHT(480),.RESET_DELAY_CYCLES(8)) dut(.*);
    task restart;
      begin
        @(negedge clk);rst_n=0;enable=0;
        repeat(5)@(negedge clk);rst_n=1;enable=1;
      end
    endtask
    initial begin
      restart;
      wait(init_done || init_error);
      if(!init_done || init_error || dut.u_sccb.writes!=253 || dut.u_sccb.reads!=9)
        $fatal(1,"Full ROM / ID / seven configuration reads failed");
      $display("PASS: 253 camera writes, 0x5640 ID and all 7 critical readbacks before init_done");
      restart;dut.u_sccb.bad_register=16'h503d;
      wait(init_done || init_error);
      if(init_done || !init_error)$fatal(1,"Incorrect color-bar setting accepted");
      $display("PASS: bad 0x503D readback prevents init_done");
      restart;dut.u_sccb.bad_register=16'h3809;
      wait(init_done || init_error);
      if(init_done || !init_error)$fatal(1,"Incorrect output width accepted");
      $display("PASS: bad resolution readback prevents init_done");
      $finish;
    end
    initial begin #1000000;$fatal(1,"Controller watchdog");end
endmodule

// Transaction-level sensor/SCCB model: tests the controller and actual ROM.
// This model does not claim to verify electrical SCCB signaling.
module sccb_master #(
    parameter CLK_HZ=50000000,SCCB_HZ=100000,TIMEOUT_CYCLES=1000000
)(input clk,rst_n,start,read,input [7:0] dev_addr,
  input [15:0] reg_addr,input [7:0] wr_data,output reg [7:0] rd_data,
  output reg busy,done,ack_error,timeout,inout sccb_sda,sccb_scl);
    reg [7:0] registers[0:65535];
    reg [15:0] bad_register;
    integer writes,reads,count;
    always @(posedge clk or negedge rst_n) begin
      if(!rst_n)begin
        busy<=0;done<=0;ack_error<=0;timeout<=0;rd_data<=0;
        writes<=0;reads<=0;count<=0;bad_register<=16'hffff;
      end else begin
        done<=0;
        if(start && !busy)begin
          busy<=1;count<=3;
          if(dev_addr!==8'h78)$fatal(1,"Wrong camera address");
          if(read)begin
            reads<=reads+1;
            if(reg_addr==16'h300a)rd_data<=8'h56;
            else if(reg_addr==16'h300b)rd_data<=8'h40;
            else begin
              if((^registers[reg_addr])===1'bx)$fatal(1,"Uninitialized sensor register %h",reg_addr);
              rd_data<=registers[reg_addr] ^ (reg_addr==bad_register ? 8'h01 : 8'h00);
            end
          end else begin registers[reg_addr]<=wr_data;writes<=writes+1;end
        end else if(busy)begin
          if(count==0)begin busy<=0;done<=1;end
          else count<=count-1;
        end
      end
    end
endmodule
