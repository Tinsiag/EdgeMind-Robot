`timescale 1ns/1ps
module mpu_driver_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0;reg [31:0] now_ms=0;
    wire start,read;wire [6:0] address;wire [7:0] reg_addr;wire [3:0] byte_count;wire [111:0] write_data;
    reg busy=0,done=0,error=0;reg [111:0] read_data=0;
    wire sample_update,valid,ready;wire signed [15:0] ax,ay,az,gx,gy,gz,temperature;
    wire [31:0] sample_time,sequence_id,errors;wire [7:0] fault,who_am_i;
    mpu6050_driver #(.ALLOW_MPU6500(1)) dut(.*);
    reg [7:0] regs[0:127];reg no_data=0,wrong_id=0,bad_config=0,fail_bus=0;
    reg model6500=0,only_high=1,bad_accel2=0;
    integer cycle=0,n,reads=0;
    always @(negedge clk) begin cycle=cycle+1;ms_tick=cycle%10==0;end
    always @(posedge clk) begin
        if(ms_tick) now_ms<=now_ms+1;
        done<=0;
        if(start) begin
            busy<=1;error<=fail_bus || (only_high && address==7'h68);
            if(read) begin
                case(reg_addr)
                    8'h75:read_data<=wrong_id ? 8'h71:model6500 ? 8'h70:8'h68;
                    8'h3a:read_data<=no_data ? 0:1;
                    8'h1d:read_data<=bad_accel2 ? 8'hff:regs[reg_addr];
                    8'h3b:begin
                        if(byte_count!=14) $fatal(1,"burst length");
                        read_data<=112'h0102fffe40000000123480007fff;reads=reads+1;
                    end
                    default:read_data<=bad_config ? 8'hff:regs[reg_addr];
                endcase
            end else regs[reg_addr]<=write_data[7:0];
        end else if(busy) begin busy<=0;done<=1;end
    end
    task reset;begin @(negedge clk);rst_n=0;repeat(3) @(negedge clk);rst_n=1;end endtask
    initial begin
        for(n=0;n<128;n=n+1) regs[n]=0;
        reset();wait(sample_update);@(negedge clk);
        if(!valid || !ready || address!=7'h69 || ay!=-2 || az!=16384 || gx!=4660 || gy!=-32768 || gz!=32767) $fatal(1,"sample or address fallback");
        if(regs[8'h19]!=9 || regs[8'h1a]!=3 || regs[8'h1b]!=8'h18 || regs[8'h1c]!=0 || regs[8'h6a]!=0) $fatal(1,"configuration");
        no_data=1;wait(fault==3);if(valid) $fatal(1,"data timeout");
        no_data=0;wait(sample_update);if(!valid) $fatal(1,"recovery");
        model6500=1;only_high=0;reset();wait(sample_update);@(negedge clk);
        if(who_am_i!=8'h70 || address!=7'h68 || !ready || !valid || regs[8'h1d]!=3)
            $fatal(1,"MPU6500 profile at 0x68");
        only_high=1;reset();wait(sample_update);@(negedge clk);
        if(address!=7'h69 || who_am_i!=8'h70 || !ready) $fatal(1,"MPU6500 high address");
        bad_accel2=1;reset();wait(fault==4);if(valid || ready) $fatal(1,"MPU6500 accel filter readback bypassed");
        bad_accel2=0;
        wrong_id=1;reset();wait(fault==2);if(valid || ready) $fatal(1,"wrong WHO_AM_I");
        wrong_id=0;bad_config=1;reset();wait(fault==4);if(valid || ready) $fatal(1,"config readback mismatch");
        bad_config=0;fail_bus=1;reset();wait(errors>=2);if(valid) $fatal(1,"NACK accepted");
        $display("PASS MPU6050/6500 identities, both addresses, model config/readback, signed samples, unknown rejection and recovery");$finish;
    end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
