`timescale 1ns/1ps
`default_nettype none
// RV32I firmware manages waypoint order. Neither the host nor CPU writes PWM.
module a741_mission_cpu #(parameter FIRMWARE_FILE="firmware/mission.hex")(
    input wire clk,rst_n,ms_tick,armed,geometry_verified,nav_busy,nav_arrived,nav_failed,
    input wire host_command,input wire [7:0] host_kind,input wire [255:0] host_payload,
    output reg host_reply_done,output reg [255:0] host_reply,
    output reg nav_command,output reg [7:0] nav_kind,output reg [255:0] nav_payload,
    input wire nav_reply_done,input wire [255:0] nav_reply,
    output wire owns,alive,fault,output reg [31:0] progress
);
    wire trap,mem_valid,mem_instr;reg mem_ready;
    wire [31:0] mem_addr,mem_wdata;wire [3:0] mem_wstrb;reg [31:0] ram_q,io_q;
    wire [31:0] mem_rdata=mem_addr<8192 ? ram_q:io_q;
    reg [31:0] ram[0:2047];
    initial $readmemh(FIRMWARE_FILE,ram);
    picorv32 #(.ENABLE_COUNTERS(0),.ENABLE_COUNTERS64(0),.BARREL_SHIFTER(1),
        .TWO_CYCLE_COMPARE(1),.TWO_CYCLE_ALU(1),.ENABLE_MUL(0),.ENABLE_DIV(0),
        .ENABLE_IRQ(0),.PROGADDR_RESET(0),.STACKADDR(8192)) cpu(
        .clk(clk),.resetn(rst_n),.trap(trap),.mem_valid(mem_valid),.mem_instr(mem_instr),
        .mem_ready(mem_ready),.mem_addr(mem_addr),.mem_wdata(mem_wdata),.mem_wstrb(mem_wstrb),.mem_rdata(mem_rdata),
        .pcpi_wr(1'b0),.pcpi_rd(32'd0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),.irq(32'd0));
    reg [31:0] now_ms,host_arg,command_arg;
    reg [7:0] host_op,command_result;
    reg [9:0] watchdog;
    reg pending,command_busy,active,abort_latched,cpu_failed;
    assign alive=!trap && watchdog<100;
    assign fault=trap || cpu_failed;
    assign owns=active;
    wire stop_request=host_command && (host_kind==3 || host_kind==4 || host_kind==8'h56 ||
        (host_kind==8'h58 && host_payload[7:0]==3) ||
        (host_kind==8'h59 && host_payload[7:0]==0));
    always @(posedge clk) begin
        if(mem_valid && !mem_ready && mem_addr<8192) begin
            // Arora V supports normal/write-through SP modes. Do not infer
            // read-before-write on store cycles; RV32 stores ignore read data.
            if(mem_wstrb==0) ram_q<=ram[mem_addr[12:2]];
            if(mem_wstrb[0]) ram[mem_addr[12:2]][7:0]<=mem_wdata[7:0];
            if(mem_wstrb[1]) ram[mem_addr[12:2]][15:8]<=mem_wdata[15:8];
            if(mem_wstrb[2]) ram[mem_addr[12:2]][23:16]<=mem_wdata[23:16];
            if(mem_wstrb[3]) ram[mem_addr[12:2]][31:24]<=mem_wdata[31:24];
        end
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            mem_ready<=0;now_ms<=0;watchdog<=100;host_arg<=0;host_op<=0;command_arg<=0;command_result<=0;
            pending<=0;command_busy<=0;active<=0;abort_latched<=0;cpu_failed<=0;io_q<=0;host_reply_done<=0;host_reply<=0;
            nav_command<=0;nav_kind<=0;nav_payload<=0;progress<=0;
        end else begin
            mem_ready<=0;host_reply_done<=0;nav_command<=0;
            if(ms_tick) begin now_ms<=now_ms+1'b1;if(watchdog<1023) watchdog<=watchdog+1'b1;end
            if(nav_reply_done && command_busy) begin command_busy<=0;command_result<=nav_reply[7:0];end
            if(host_command && host_kind==8'h58) begin
                if(pending || host_payload[7:0]>4) begin host_reply_done<=1;host_reply<=3;end
                else begin pending<=1;host_op<=host_payload[7:0];host_arg<=host_payload[39:8];end
            end
            if(mem_valid && !mem_ready) begin
                mem_ready<=1;
                if(mem_addr>=8192) begin
                    io_q<=0;
                    if(mem_addr[31:8]!=24'h100000) abort_latched<=1;
                    else if(|mem_wstrb) case(mem_addr[7:0])
                        16:if(pending) begin
                            pending<=0;host_reply_done<=1;host_reply<=0;
                            host_reply[7:0]<=mem_wdata[7:0];host_reply[15:8]<={5'd0,fault,alive,active};
                            host_reply[63:32]<=progress;
                        end
                        20:if(!command_busy && active && alive && !abort_latched &&
                              (mem_wdata==8'h54 || mem_wdata==8'h55)) begin
                            nav_command<=1;nav_kind<=mem_wdata[7:0];nav_payload<={224'd0,command_arg};
                            command_busy<=1;command_result<=0;
                        end
                        24:command_arg<=mem_wdata;
                        32:begin
                            if(mem_wdata==0) active<=0;
                            else if(armed && geometry_verified && alive && !abort_latched) active<=1;
                        end
                        36:if(mem_wdata==32'h0741c0de) watchdog<=0;
                        40:progress<=mem_wdata;
                        default:;
                    endcase
                    else case(mem_addr[7:0])
                        0:io_q<={26'd0,nav_busy,nav_arrived,nav_failed,(abort_latched || fault),geometry_verified,armed};
                        4:io_q<=now_ms;
                        8:io_q<={23'd0,pending,host_op};
                        12:io_q<=host_arg;
                        28:io_q<={23'd0,command_busy,command_result};
                        default:;
                    endcase
                end
            end
            if(!armed && !active && !pending && !command_busy) abort_latched<=0;
            // STOP has priority even over a simultaneous firmware ACTIVE write.
            if(trap || (active && watchdog>=100)) cpu_failed<=1;
            if(stop_request || trap || (active && watchdog>=100)) begin active<=0;abort_latched<=1;command_busy<=0;end
        end
endmodule
`default_nettype wire
