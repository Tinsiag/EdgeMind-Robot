`timescale 1ns/1ps
module mpu_i2c_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,read=1;reg [6:0] address=7'h68;reg [7:0] reg_addr=8'h3b;
    reg [3:0] byte_count=14;reg [111:0] write_data=0;
    wire [111:0] read_data;wire busy,done,error;
    tri1 sda,scl;reg slave_low=0,hold_clock=0,nack=0;
    assign sda=slave_low ? 1'b0:1'bz;assign scl=hold_clock ? 1'b0:1'bz;
    a741_imu_i2c #(.CLK_HZ(1000000),.I2C_HZ(25000),.TIMEOUT_CYCLES(100000)) dut(.*);
    reg [111:0] value=112'h0102fffe40000000123480007fff;
    reg [7:0] octet=0;integer bytes=0,acks=0;
    always @* begin
        slave_low=0;
        if(dut.state>=7 && dut.state<=10) slave_low=!nack;
        if(dut.state>=14 && dut.state<=17) slave_low=!value[(13-dut.data_index)*8+dut.bit_index];
    end
    always @(posedge scl) if(rst_n) begin
        if(dut.state==5) begin
            octet={octet[6:0],sda};
            if(dut.bit_index==0) begin
                case(bytes)
                    0:if(octet!=8'hd0) $fatal(1,"MPU address");
                    1:if(octet!=8'h3b) $fatal(1,"MPU must use one register byte");
                    2:if(octet!=8'hd1) $fatal(1,"repeated read address");
                    default:$fatal(1,"unexpected register header byte");
                endcase
                bytes=bytes+1;
            end
        end
        if(dut.state==20) begin
            if(sda!==(dut.data_index==13)) $fatal(1,"final NACK / preceding ACK");
            acks=acks+1;
        end
    end
    task transfer;begin @(negedge clk);start=1;@(negedge clk);start=0;wait(done);@(negedge clk);end endtask
    initial begin
        #50;rst_n=1;transfer();
        if(error || read_data!==value || bytes!=3 || acks!=14) $fatal(1,"14-byte burst");
        bytes=0;nack=1;transfer();if(!error) $fatal(1,"NACK ignored");
        bytes=0;nack=0;hold_clock=1;transfer();if(!error || busy) $fatal(1,"stuck bus");
        $display("PASS MPU6050 8-bit register, 14-byte burst, repeated START, ACK/NACK, stuck bus");$finish;
    end
    initial begin #3000000;$fatal(1,"watchdog");end
endmodule
