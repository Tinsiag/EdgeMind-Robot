`timescale 1ns/1ps
module tof_driver_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0;wire xshut_low,xfer_start,xfer_read;
    wire [15:0] xfer_reg;wire [2:0] xfer_count;wire [31:0] xfer_write;
    reg xfer_busy=0,xfer_done=0,xfer_error=0;reg [31:0] xfer_data=0;
    wire init_done,error,sample_update,sample_valid;wire [15:0] distance_mm;wire [7:0] range_status;
    vl53l1x_driver #(.BOOT_TIMEOUT_MS(500)) dut(.*);
    integer ticks=0,transactions=0,config_writes=0,clears=0;
    reg inject_error=0,not_ready=0;reg [7:0] sensor_status=9;
    reg [7:0] regs[0:511];integer i;
    always @(negedge clk) begin ticks=ticks+1;ms_tick=ticks%10==0;end
    always @(posedge clk) begin
        xfer_done<=0;
        if(!rst_n)begin xfer_busy<=0;xfer_done<=0;config_writes<=0;clears<=0;transactions<=0;end
        else if(xfer_start)begin
            xfer_busy<=1;xfer_error<=inject_error;transactions<=transactions+1;
            if(xfer_read)case(xfer_reg)
                16'he5:xfer_data<=1;
                16'h10f:xfer_data<=16'heacc;
                16'h31:xfer_data<=not_ready?0:1;
                16'hde:xfer_data<=200;
                16'h89:xfer_data<=sensor_status;
                16'h96:xfer_data<=750;
                default:$fatal(1,"Unexpected register read %h",xfer_reg);
            endcase
            else begin
                if(xfer_reg>=16'h2d && xfer_reg<=16'h87 && config_writes<91) begin
                    if(xfer_reg!=16'h2d+config_writes)$fatal(1,"Configuration order");
                    config_writes<=config_writes+1;
                end
                for(i=0;i<xfer_count;i=i+1) regs[xfer_reg+i]<=xfer_write >> ((xfer_count-1-i)*8);
                if(xfer_reg==16'h86)clears<=clears+1;
                if(config_writes==91 && xfer_reg==16'h6c && xfer_write!=10750)$fatal(1,"Oscillator-scaled period wrong %d",xfer_write);
            end
        end else if(xfer_busy)begin xfer_busy<=0;xfer_done<=1;end
    end
    task reset;begin @(negedge clk);rst_n=0;repeat(3)@(negedge clk);rst_n=1;end endtask
    initial begin
        reset;wait(sample_update);@(negedge clk);
        if(!init_done || error || !sample_valid || distance_mm!=750 || config_writes!=91 || clears<2)$fatal(1,"Ranging sequence failed");
        if(regs[16'h5e]!=0 || regs[16'h5f]!=8'h60 || regs[16'h61]!=0 || regs[16'h62]!=8'h6e)$fatal(1,"33ms configuration missing");
        sensor_status=4;wait(!sample_update);wait(sample_update);@(negedge clk);
        if(sample_valid)$fatal(1,"Invalid range accepted");
        inject_error=1;wait(error);if(sample_valid)$fatal(1,"NACK did not invalidate range");
        inject_error=0;not_ready=1;reset;wait(error);
        if(init_done)$fatal(1,"Data-not-ready timeout accepted");
        $display("PASS: ST configuration, calibration, scaled period, valid/invalid samples, NACK and timeout");$finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
