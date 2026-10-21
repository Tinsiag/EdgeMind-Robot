`timescale 1ns/1ps
`default_nettype none
// EMS1: 112-byte sensor/motion snapshot. EML1: 64-byte CRC-checked LD06 packet.
// Both are sent on UDP 6103; snapshots are atomic under arbitrary backpressure.
module a741_telemetry #(parameter PHY_DIAGNOSTICS=0)(
    input wire clk,rst_n,ms_tick,input wire [895:0] snapshot,
    input wire [255:0] phy_snapshot,
    input wire lidar_update,input wire [375:0] lidar_packet,
    input wire [31:0] lidar_time,lidar_seq,
    output wire [7:0] data,output wire valid,last,
    output wire [15:0] length,input wire ready,
    output reg [31:0] dropped
);
    reg [895:0] tx_buffer;
    reg [511:0] pending;
    reg pending_valid,busy;
    reg [6:0] index,size;
    reg [5:0] period;
    reg snapshot_due;
    reg phy_due;
    reg [4:0] phy_period;
    assign data=tx_buffer[index*8+:8];assign valid=busy;
    assign last=busy && index==size-1;assign length={9'd0,size};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin tx_buffer<=0;pending<=0;pending_valid<=0;busy<=0;index<=0;size<=0;period<=0;snapshot_due<=0;dropped<=0;phy_due<=0;phy_period<=0;end
        else begin
            if(ms_tick) begin
                if(period==49) begin
                    period<=0;snapshot_due<=1;
                    if(PHY_DIAGNOSTICS) begin
                        if(phy_period==19) begin phy_period<=0;phy_due<=1;end
                        else phy_period<=phy_period+1'b1;
                    end
                end
                else period<=period+1'b1;
            end
            if(lidar_update) begin
                if(pending_valid) dropped<=dropped+1'b1;
                pending<= {8'd0,lidar_packet,lidar_time,lidar_seq,16'd64,16'd1,32'h314c4d45};
                pending_valid<=1;
            end
            if(!busy) begin
                if(PHY_DIAGNOSTICS && phy_due) begin
                    tx_buffer<={640'd0,phy_snapshot};size<=32;index<=0;busy<=1;phy_due<=0;
                end
                else if(snapshot_due) begin tx_buffer<=snapshot;size<=112;index<=0;busy<=1;snapshot_due<=0;end
                else if(pending_valid && !lidar_update) begin tx_buffer<={384'd0,pending};size<=64;index<=0;busy<=1;pending_valid<=0;end
            end else if(ready) begin
                if(index==size-1) busy<=0;else index<=index+1'b1;
            end
        end
endmodule
`default_nettype wire
