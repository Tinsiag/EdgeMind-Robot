`timescale 1ns/1ps
`default_nettype none
// RTL8211F-CG startup/identity check.
// RXDLY/TXDLY are power-on strap pins on RTL8211F.  The datasheet defines
// only bit 6 in page 0xd08/reg 0x15; do not write undocumented/reserved bits.
module a741_phy_init #(parameter CLK_HZ=50000000,RESET_MS=10,SETTLE_MS=50,TIMEOUT_MS=100)(
    input wire clk,rst_n,done,input wire [15:0] read_data,
    output reg phy_reset_n,ready,error,go,read_mode,
    output reg [4:0] register_address,output reg [15:0] write_data,
    output reg [31:0] identity,output reg [15:0] bmsr_initial,bmcr,bmsr_current,
    output reg [3:0] fault
);
    localparam HOLD_RESET=0,SETTLE=1,ISSUE=2,LAUNCH=3,WAIT_DONE=4,GAP=5,FINISHED=6,FAILED=7;
    reg [2:0] state;
    reg [3:0] step;
    reg [31:0] timer;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=HOLD_RESET;step<=0;timer<=0;phy_reset_n<=0;ready<=0;error<=0;
            go<=0;read_mode<=1;register_address<=0;write_data<=0;
            identity<=0;bmsr_initial<=0;bmcr<=0;bmsr_current<=0;fault<=0;
        end else begin
            go<=0;
            case(state)
                HOLD_RESET: if(timer>=CLK_HZ/1000*RESET_MS-1) begin
                    phy_reset_n<=1;timer<=0;state<=SETTLE;
                end else timer<=timer+1'b1;
                SETTLE: if(timer>=CLK_HZ/1000*SETTLE_MS-1) begin
                    timer<=0;state<=ISSUE;
                end else timer<=timer+1'b1;
                ISSUE: begin
                    // Present the MDIO command first.  The bit engine samples
                    // Mode/Reg_addr when Go is asserted, so launch one clock
                    // later after these nonblocking assignments have settled.
                    go<=0;timer<=0;state<=LAUNCH;
                    case(step)
                        0:begin read_mode<=1;register_address<=2;end // PHYID1
                        1:begin read_mode<=1;register_address<=3;end // PHYID2
                        2:begin read_mode<=1;register_address<=1;end // BMSR
                        3:begin read_mode<=1;register_address<=0;end // BMCR
                        4:begin read_mode<=1;register_address<=1;end // BMSR latch refresh
                        default:begin go<=0;error<=1;fault<=4;state<=FAILED;end
                    endcase
                end
                LAUNCH: begin
                    go<=1;timer<=0;state<=WAIT_DONE;
                end
                WAIT_DONE: if(done) begin
                    timer<=0;state<=GAP;
                    case(step)
                        0:identity[31:16]<=read_data;
                        1:begin
                            identity[15:0]<=read_data;
                            if(identity[31:16]!=16'h001c || (read_data&16'hfff0)!=16'hc910) begin
                                error<=1;fault<=1;state<=FAILED;
                            end
                        end
                        2:bmsr_initial<=read_data;
                        3:begin
                            bmcr<=read_data;
                            if(read_data[15]) begin error<=1;fault<=3;state<=FAILED;end
                        end
                        4:begin
                            bmsr_current<=read_data;
                            ready<=1;state<=FINISHED;
                        end
                        default:;
                    endcase
                end else if(timer>=CLK_HZ/1000*TIMEOUT_MS-1) begin
                    error<=1;fault<=4;state<=FAILED;
                end else timer<=timer+1'b1;
                GAP: if(timer==3) begin step<=step+1'b1;timer<=0;state<=ISSUE;end
                     else timer<=timer+1'b1;
                FINISHED:;
                FAILED:;
                default:begin error<=1;fault<=4;state<=FAILED;end
            endcase
        end
endmodule
`default_nettype wire
