`timescale 1ns/1ps
module board_platform_tb;
    reg clk=0,rst_n=0;
    always #10 clk=~clk;
    tri1 scl,sda;
    wire camera_reset_n,ready,error;
    ov5640_board_init #(.CLK_HZ(1000000)) dut(.*);
    task restart;
        begin
            @(negedge clk);rst_n=0;
            repeat(3) @(negedge clk);
            rst_n=1;
        end
    endtask
    initial begin
        restart;
        wait(ready || error);
        if(!ready || error || dut.init.u_sccb.writes!=254 || dut.init.u_sccb.reads!=2 || dut.verify.reads!=9)
            $fatal(1,"FAIL camera ROM/init/readback counts");
        if(dut.init.u_sccb.regs[16'h3808]!=3 || dut.init.u_sccb.regs[16'h3809]!=32 ||
           dut.init.u_sccb.regs[16'h380a]!=1 || dut.init.u_sccb.regs[16'h380b]!=224 ||
           dut.init.u_sccb.regs[16'h4300]!=8'h61 || dut.init.u_sccb.regs[16'h501f]!=1 ||
           dut.init.u_sccb.regs[16'h5001]!=8'ha3 || dut.init.u_sccb.regs[16'h503d]!=0 ||
           dut.init.u_sccb.regs[16'h4741]!=0) $fatal(1,"FAIL actual camera table settings");
        restart;
        dut.verify.bad_register=16'h503d;
        wait(ready || error);
        if(ready || !error) $fatal(1,"FAIL incorrect readback accepted");
        restart;
        dut.init.u_sccb.bad_register=16'h300b;
        wait(ready || error);
        if(ready || !error) $fatal(1,"FAIL incorrect sensor ID accepted");
        $display("PASS board camera: 254 actual ROM writes, ID/readbacks, bad ID/config rejection");
        $finish;
    end
    initial begin #3000000;$fatal(1,"FAIL camera test timeout");end
endmodule

// Transaction model checks controller sequencing, not electrical SCCB timing.
module sccb_master #(parameter CLK_HZ=50000000,SCCB_HZ=100000,TIMEOUT_CYCLES=1000000)(
    input clk,rst_n,start,read,input [7:0] dev_addr,input [15:0] reg_addr,
    input [7:0] wr_data,output reg [7:0] rd_data,output reg busy,done,ack_error,timeout,
    inout sccb_sda,sccb_scl
);
    reg [7:0] regs[0:65535];
    reg [15:0] bad_register;
    integer writes,reads,count;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            busy<=0;done<=0;ack_error<=0;timeout<=0;rd_data<=0;
            writes<=0;reads<=0;count<=0;bad_register<=16'hffff;
        end else begin
            done<=0;
            if(start && !busy) begin
                if(dev_addr!==8'h78) $fatal(1,"FAIL SCCB address");
                busy<=1;count<=3;
                if(read) begin
                    reads<=reads+1;
                    case(reg_addr)
                        16'h300a:rd_data<=8'h56;
                        16'h300b:rd_data<=8'h40 ^ (reg_addr==bad_register);
                        16'h3808:rd_data<=3;
                        16'h3809:rd_data<=32;
                        16'h380a:rd_data<=1;
                        16'h380b:rd_data<=224;
                        16'h4300:rd_data<=8'h61;
                        16'h501f:rd_data<=1;
                        16'h5001:rd_data<=8'ha3;
                        16'h503d:rd_data<=reg_addr==bad_register;
                        16'h4741:rd_data<=0;
                        default:$fatal(1,"FAIL unexpected read %h",reg_addr);
                    endcase
                end else begin
                    if((^wr_data)===1'bx || (^reg_addr)===1'bx) $fatal(1,"FAIL undefined ROM");
                    regs[reg_addr]<=wr_data;writes<=writes+1;
                end
            end else if(busy) begin
                if(count==0) begin busy<=0;done<=1;end
                else count<=count-1;
            end
        end
endmodule
