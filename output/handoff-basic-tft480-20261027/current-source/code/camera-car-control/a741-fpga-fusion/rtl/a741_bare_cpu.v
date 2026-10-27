`timescale 1ns/1ps
`default_nettype none
// Bare RV32I supervisor: uptime and a 100ms watchdog, no navigation interface.
module a741_bare_cpu #(parameter FIRMWARE_FILE="firmware/mission.hex")(
    input wire clk,rst_n,ms_tick,armed,
    output wire alive,output reg fault,output reg [31:0] progress
);
    wire trap,mem_valid,mem_instr;reg mem_ready;
    wire [31:0] mem_addr,mem_wdata;wire [3:0] mem_wstrb;reg [31:0] ram_q,io_q;
    wire [31:0] mem_rdata=mem_addr<8192 ? ram_q:io_q;
    reg [31:0] ram[0:2047];
    reg [31:0] now_ms;reg [9:0] watchdog;reg seen;
    initial $readmemh(FIRMWARE_FILE,ram);
    picorv32 #(.ENABLE_COUNTERS(0),.ENABLE_COUNTERS64(0),.BARREL_SHIFTER(1),
        .TWO_CYCLE_COMPARE(1),.TWO_CYCLE_ALU(1),.ENABLE_MUL(0),.ENABLE_DIV(0),
        .ENABLE_IRQ(0),.PROGADDR_RESET(0),.STACKADDR(8192)) cpu(
        .clk(clk),.resetn(rst_n),.trap(trap),.mem_valid(mem_valid),.mem_instr(mem_instr),
        .mem_ready(mem_ready),.mem_addr(mem_addr),.mem_wdata(mem_wdata),.mem_wstrb(mem_wstrb),.mem_rdata(mem_rdata),
        .pcpi_wr(1'b0),.pcpi_rd(32'd0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),.irq(32'd0));
    assign alive=seen && !trap && !fault && watchdog<100;
    always @(posedge clk) begin
        if(mem_valid && !mem_ready && mem_addr<8192) begin
            // Arora V SP RAM supports normal/write-through, not read-before-
            // write. RV32 stores ignore read data: hold ram_q on store cycles.
            if(mem_wstrb==0) ram_q<=ram[mem_addr[12:2]];
            if(mem_wstrb[0]) ram[mem_addr[12:2]][7:0]<=mem_wdata[7:0];
            if(mem_wstrb[1]) ram[mem_addr[12:2]][15:8]<=mem_wdata[15:8];
            if(mem_wstrb[2]) ram[mem_addr[12:2]][23:16]<=mem_wdata[23:16];
            if(mem_wstrb[3]) ram[mem_addr[12:2]][31:24]<=mem_wdata[31:24];
        end
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin mem_ready<=0;io_q<=0;now_ms<=0;watchdog<=0;seen<=0;fault<=0;progress<=0;end
        else begin
            mem_ready<=0;
            if(ms_tick) begin now_ms<=now_ms+1'b1;if(watchdog<1023) watchdog<=watchdog+1'b1;end
            if(mem_valid && !mem_ready) begin
                mem_ready<=1;
                if(mem_addr>=8192) begin
                    io_q<=0;
                    if(mem_addr[31:8]!=24'h100000) fault<=1;
                    else if(|mem_wstrb) case(mem_addr[7:0])
                        36:if(mem_wdata==32'h0741c0de) begin watchdog<=0;seen<=1;end
                        40:progress<=mem_wdata;
                        default:;
                    endcase
                    else case(mem_addr[7:0])
                        0:io_q<={31'd0,armed};
                        4:io_q<=now_ms;
                        default:;
                    endcase
                end
            end
            if(trap || (armed && watchdog>=100)) fault<=1;
        end
endmodule
`default_nettype wire
