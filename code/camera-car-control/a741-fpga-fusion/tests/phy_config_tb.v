`timescale 1ns/1ps
// Pin-level Clause 22 responder. No hierarchy into the controller is used.
module phy_config_tb;
reg clk=0,rst_n=0; always #10 clk=~clk;
wire phy_rst_n,ready,error,mdc; tri1 mdio;
reg phy_low=0;
assign mdio=phy_low ? 1'b0:1'bz;
a741_phy_config #(.CLOCK_HZ(50000000),.MDC_HZ(500000),.RESET_CYCLES(8),.WAIT_CYCLES(16)) dut(
    .clk(clk),.rst_n(rst_n),.phy_rst_n(phy_rst_n),.ready(ready),.error(error),.mdc(mdc),.mdio(mdio));
integer bitno=0,transactions=0,mode=0;
reg [63:0] frame=0;
reg [15:0] page=0,txreg=16'ha055,rxreg=16'hb5a0,bmcr=0,answer;
reg reading;
reg [4:0] addr;
always @(negedge phy_rst_n) begin
    bitno=0;transactions=0;frame=0;phy_low=0;
    page=0;txreg=16'ha055;rxreg=16'hb5a0;bmcr=0;
end
// A real PHY may update read data up to 300 ns after rising MDC.
// The host must sample the previous bit, then see this response next edge.
always @(posedge mdc) if(phy_rst_n) begin
    frame={frame[62:0],mdio};
    if(bitno==45) begin
        if(frame[45:14]!==32'hffffffff || frame[13:12]!==2'b01 ||
           frame[9:5]!==5'd5 || (frame[11:10]!==2'b10 && frame[11:10]!==2'b01))
            $fatal(1,"Invalid MDIO preamble/header %h",frame);
        reading=(frame[11:10]==2'b10);addr=frame[4:0];
        case(addr)
            2: answer=(mode==1)?16'hffff:16'h001c;
            3: answer=16'hc916;
            17: begin if(page!=16'h0d08) $fatal(1,"TX page");answer=txreg;end
            21: begin if(page!=16'h0d08) $fatal(1,"RX page");answer=rxreg;end
            0: begin if(page!=0) $fatal(1,"BMCR page");answer=(mode==5)?0:bmcr;end
            31: answer=page;
            default: $fatal(1,"Unexpected register");
        endcase
    end
    if(reading && bitno==46) phy_low <= #300 (mode!=2);
    if(reading && bitno>=47 && bitno<=62) phy_low <= #300 (mode!=2 && !answer[62-bitno]);
    if(bitno==63) begin
        transactions=transactions+1;
        if(!reading) begin
            if(frame[17:16]!==2'b10) $fatal(1,"Write turnaround");
            case(addr)
                31: page=frame[15:0];
                17: if(mode!=3) txreg=frame[15:0];
                21: if(mode!=4) rxreg=frame[15:0];
                0: bmcr=frame[15:0];
                default: $fatal(1,"Unexpected write");
            endcase
        end
        bitno=0;phy_low <= #300 0;
    end else bitno=bitno+1;
end
task reset_case(input integer value);
begin
    @(negedge clk);rst_n=0;#1000;
    mode=value;bitno=0;transactions=0;frame=0;phy_low=0;
    page=0;txreg=16'ha055;rxreg=16'hb5a0;bmcr=0;reading=0;
    @(negedge clk);rst_n=1;
end endtask
integer m,stopped;
initial begin
    reset_case(0);
    wait(ready || error);#1;
    if(!ready || error || transactions!=12 || page!=0 || txreg!=16'ha155 || rxreg!=16'hb5a8 || bmcr!=16'h1200)
        $fatal(1,"Configuration/RMW failed ready=%b error=%b transactions=%d tx=%h rx=%h",ready,error,transactions,txreg,rxreg);
    #4000;if(mdio!==1'b1 || mdc!==0) $fatal(1,"Bus not released");
    for(m=1;m<=5;m=m+1) begin
        reset_case(m);wait(ready || error);#1;
        if(ready || !error) $fatal(1,"Fault %d published ready",m);
        stopped=transactions;#10000;
        if(transactions!=stopped || mdio!==1'b1 || mdc!==0) $fatal(1,"Fault retried/bus busy");
    end
    reset_case(0);repeat(20) @(posedge mdc);
    reset_case(0);wait(ready || error);#1;
    if(!ready || error || transactions!=12) $fatal(1,"Mid-frame reset recovery");
    $display("PASS PHY: complete pin-level frames, RMW, ID, missing ACK, TX/RX/BMCR failures, reset recovery");$finish;
end
initial begin #20000000;$fatal(1,"PHY timeout");end
endmodule
