`timescale 1ns/1ps
module i2c_master_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,read=0;reg [6:0] address=7'h29;reg [15:0] reg_addr=16'h96;
    reg [2:0] byte_count=2;reg [31:0] write_data=32'habcd;
    wire [31:0] read_data;wire busy,done,error;
    tri1 sda,scl;reg slave_low=0,hold_clock=0,nack=0;
    assign sda=slave_low?1'b0:1'bz;assign scl=hold_clock?1'b0:1'bz;
    i2c_reg_master #(.CLK_HZ(1000000),.I2C_HZ(25000),.TIMEOUT_CYCLES(50000)) dut(.*);
    reg [15:0] sensor_value=16'h1234;
    integer received=0;reg [7:0] last_byte=0;
    // State-aware electrical peer checks actual bit wires and generates ACK.
    // Read-byte order and final master NACK are independently asserted.
    always @* begin
        slave_low=0;
        if(dut.state>=7 && dut.state<=10)slave_low=!nack;
        if(dut.state>=14 && dut.state<=17)
            slave_low=!sensor_value[(1-dut.data_index)*8+dut.bit_index];
    end
    always @(posedge scl) if(rst_n && dut.state==5)begin
        last_byte={last_byte[6:0],sda};
        if(dut.bit_index==0)begin
            case(received)
                0:if(last_byte!=8'h52)$fatal(1,"7-bit address not shifted correctly");
                1:if(last_byte!=8'h00)$fatal(1,"Register high byte");
                2:if(last_byte!=8'h96)$fatal(1,"Register low byte");
                default:;
            endcase
            received=received+1;
        end
    end
    task transfer;begin @(negedge clk);start=1;@(negedge clk);start=0;wait(done);@(negedge clk);end endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        transfer;if(error)$fatal(1,"Write got unexpected error");
        received=0;read=1;transfer;
        if(error || read_data!=32'h1234)$fatal(1,"Read/repeated START/endian failed %h",read_data);
        received=0;nack=1;transfer;if(!error)$fatal(1,"NACK ignored");nack=0;
        hold_clock=1;transfer;if(!error || busy)$fatal(1,"Stuck SCL not bounded");
        hold_clock=0;
        $display("PASS: open-drain I2C write/read, repeated START, byte order, NACK and stuck clock timeout");$finish;
    end
    initial begin #2000000;$fatal(1,"Watchdog");end
endmodule
