`timescale 1ns/1ps
module ethernet_io_tb;
GSR GSR(.GSRI(1'b1));
reg rx_clk=0,hclk=0,reset_n=0;
always #4 rx_clk=~rx_clk;
always #2 hclk=~hclk;
reg [3:0] rxd=0;reg ctl=0;
wire [7:0] data;wire valid,err,tx_clk;
acg720_rgmii_rx #(.INPUT_DELAY_TAPS(64)) dut(.rx_clk(rx_clk),.rxd(rxd),.rx_ctl(ctl),.gmii_data(data),.gmii_valid(valid),.gmii_error(err));
CLKDIV #(.DIV_MODE("2")) divider(.HCLKIN(hclk),.RESETN(reset_n),.CALIB(1'b0),.CLKOUT(tx_clk));
reg [7:0] words[0:79];reg dvs[0:79],ers[0:79];
integer i,checked=0;realtime last_edge;
initial begin
    #1;reset_n=0;#12;reset_n=1;
    repeat(8) @(posedge tx_clk);
    last_edge=$realtime;
    repeat(100) begin
        @(tx_clk);
        if($realtime-last_edge!=4.0) $fatal(1,"CLKDIV wrong pulse width");
        last_edge=$realtime;
    end
    #1;reset_n=0;#1;
    if(tx_clk!==0) $fatal(1,"CLKDIV reset");
    #15;reset_n=1;repeat(8) @(posedge tx_clk);
    last_edge=$realtime;@(posedge tx_clk);
    if($realtime-last_edge!=8.0) $fatal(1,"CLKDIV restart");
    wait(checked==77);
    $display("PASS Ethernet IO: vendor CLKDIV duty/reset and IODELAY+IDDR byte/DV/error alignment");$finish;
end
initial begin
    for(i=0;i<80;i=i+1)begin
        words[i]=(i*73)^8'ha6;dvs[i]=(i%5!=0);ers[i]=(i%7==0);
    end
    // Data changes 2 ns after the preceding clock edge, inside the specified
    // 1..3 ns arrival window. Compare whole words after the IDDR pipeline.
    @(negedge rx_clk);
    for(i=0;i<80;i=i+1)begin
        #2;rxd=words[i][3:0];ctl=dvs[i];
        @(posedge rx_clk);#0.1;
        if(i>=3)begin
            if(data!==words[i-2] || valid!==dvs[i-2] || err!==ers[i-2])
                $fatal(1,"RGMII alignment i=%d got=%h expected=%h dv=%b er=%b",i,data,words[i-2],valid,err);
            checked=checked+1;
        end
        #1.9;rxd=words[i][7:4];ctl=dvs[i]^ers[i];
        @(negedge rx_clk);
    end
end
initial begin #10000;$fatal(1,"Ethernet IO timeout");end
endmodule
