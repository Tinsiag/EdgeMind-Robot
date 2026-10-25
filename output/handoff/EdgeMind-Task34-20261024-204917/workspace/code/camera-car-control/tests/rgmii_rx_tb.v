`timescale 1ns/1ps
module rgmii_rx_tb;
    reg rx_clk=0;
    always #4 rx_clk=~rx_clk;
    reg [3:0] rxd=0;
    reg rx_ctl=0;
    wire [7:0] gmii_data;
    wire gmii_valid,gmii_error;
    GSR GSR(.GSRI(1'b1));
    acg720_rgmii_rx dut(.*);
    reg [7:0] data[0:7];
    reg [1:0] flags[0:7];
    integer n;
    initial begin
        data[0]=8'h00;data[1]=8'hd5;data[2]=8'h12;data[3]=8'ha7;
        data[4]=8'h3c;data[5]=8'h00;data[6]=8'h00;data[7]=8'h00;
        flags[0]=0;flags[1]=1;flags[2]=1;flags[3]=3;
        flags[4]=1;flags[5]=0;flags[6]=0;flags[7]=0;
        // Drive one nanosecond after each preceding clock edge.
        for(n=0;n<8;n=n+1) begin
            #1;rxd=data[n][3:0];rx_ctl=flags[n][0];
            @(posedge rx_clk);#1;rxd=data[n][7:4];rx_ctl=flags[n][0]^flags[n][1];
            #1;
            if(n>=2 && (gmii_data!==data[n-2] || gmii_valid!==flags[n-2][0] || gmii_error!==flags[n-2][1]))
                $fatal(1,"FAIL RGMII byte/valid/error alignment n=%0d data=%h",n,gmii_data);
            @(negedge rx_clk);
        end
        $display("PASS RGMII RX against Gowin IDDR model: nibble alignment, DV, error");
        $finish;
    end
endmodule
