`timescale 1ns/1ps
module phy_init_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,done=0;reg [15:0] read_data=0;
    wire phy_reset_n,ready,error,go,read_mode;
    wire [4:0] register_address;wire [15:0] write_data;
    wire [31:0] identity;wire [15:0] bmsr_initial,bmcr,bmsr_current;wire [3:0] fault;
    a741_phy_init #(.CLK_HZ(1000),.TIMEOUT_MS(100)) dut(.*);
    reg [15:0] page;
    reg [2:0] pending;
    integer mode,transactions,i,reset_cycles,settle_cycles;
    always @(negedge clk) begin
        done=0;
        if(!rst_n) begin pending=0;page=0;transactions=0;reset_cycles=0;settle_cycles=0;end
        else if(go) begin
            if(!phy_reset_n || reset_cycles<10 || settle_cycles<50)
                $fatal(1,"MDIO before 10ms reset and 50ms settling");
            transactions=transactions+1;pending=3;read_data=0;
            if(read_mode) begin
                if(register_address==2) read_data=mode==1 ? 16'hffff:16'h001c;
                else if(register_address==3) read_data=16'hc916;
                else if(register_address==1) read_data=transactions==3 ? 16'h7949:16'h796d;
                else if(register_address==0) read_data=mode==2 ? 16'h9140:16'h1140;
                else $fatal(1,"unexpected read page/reg %h/%d",page,register_address);
            end else begin
                $fatal(1,"startup must not write RTL8211F registers");
            end
        end else if(pending!=0) begin
            pending=pending-1;
            if(pending==0 && mode!=3) done=1;
        end
        if(rst_n) begin
            if(!phy_reset_n) reset_cycles=reset_cycles+1;
            else settle_cycles=settle_cycles+1;
        end
    end
    initial begin
        for(mode=0;mode<4;mode=mode+1) begin
            rst_n=0;repeat(4) @(posedge clk);#1;rst_n=1;
            for(i=0;i<300 && !ready && !error;i=i+1) begin @(posedge clk);#1;end
            if(mode==0) begin
                if(!ready || error || identity!=32'h001cc916 || bmsr_initial!=16'h7949 ||
                   bmcr!=16'h1140 || bmsr_current!=16'h796d || transactions!=5)
                    $fatal(1,"normal PHY identity/status read failed");
            end else if(mode==1) begin
                if(ready || !error || transactions!=2 || fault!=1) $fatal(1,"unknown identity accepted");
            end else if(mode==2) begin
                if(ready || !error || fault!=3) $fatal(1,"BMCR reset state ignored");
            end else if(ready || !error || fault!=4) $fatal(1,"MDIO timeout not bounded");
        end
        $display("PASS RTL8211F read-only identity/status, reset settle and MDIO timeout");$finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule
