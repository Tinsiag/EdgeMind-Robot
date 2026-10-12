`timescale 1ns/1ps
module uart_loopback_tb;
    reg clk=0, rstn=0, start=0; reg [7:0] tx_data=0; wire tx,busy; wire [7:0] rx_data; wire rx_valid;
    always #5 clk=~clk;
    uart_tx #(.CLK_HZ(5000000),.BAUD(100000)) txu(.clk(clk),.rstn(rstn),.start(start),.data(tx_data),.tx(tx),.busy(busy));
    uart_rx #(.CLK_HZ(5000000),.BAUD(100000)) rxu(.clk(clk),.rstn(rstn),.rx(tx),.data(rx_data),.valid(rx_valid),.framing_error());
    initial begin
        #20; rstn=1; @(negedge clk); tx_data=8'hA5; start=1; @(negedge clk); start=0;
        wait(rx_valid); if(rx_data!==8'hA5) $fatal(1,"UART loopback mismatch %h",rx_data);
        $display("PASS UART loopback"); $finish;
    end
    initial begin #100000 $fatal(1,"UART watchdog"); end
endmodule
