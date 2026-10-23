`timescale 1ns/1ps
`default_nettype none
// 128x128 two-bit occupancy map with bounded clear, update and read ports.
// Values: 00 unknown, 01 observed free, 10 occupied, 11 reserved.
module a741_grid_map(
    input wire clk,rst_n,clear,
    input wire write_valid,input wire [6:0] write_x,write_y,input wire [1:0] write_value,
    input wire read_valid,input wire [13:0] read_address,
    output reg [1:0] read_value,output reg read_done,
    output reg clear_busy,output reg map_valid,output reg [13:0] write_count
);
    reg [1:0] cells[0:16383];
    reg [13:0] clear_address;
    wire [13:0] write_address={write_y,write_x};

    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            clear_address<=0;clear_busy<=0;map_valid<=0;read_value<=0;read_done<=0;write_count<=0;
        end else begin
            read_done<=0;
            if(clear && !clear_busy) begin
                clear_busy<=1;clear_address<=0;map_valid<=0;write_count<=0;
            end else if(clear_busy) begin
                cells[clear_address]<=2'b00;
                if(clear_address==14'd16383) begin clear_busy<=0;map_valid<=1;end
                else clear_address<=clear_address+1'b1;
            end else begin
                if(write_valid && map_valid) begin
                    cells[write_address]<=write_value;write_count<=write_count+1'b1;
                end
                if(read_valid && map_valid) begin
                    read_value<=cells[read_address];read_done<=1;
                end
            end
        end
endmodule
`default_nettype wire
