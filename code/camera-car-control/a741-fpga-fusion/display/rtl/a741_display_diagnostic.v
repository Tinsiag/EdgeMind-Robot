`timescale 1ns/1ps
`default_nettype none
// Opt-in, motor-locked diagnostic. The panel scanner and J1 wiring are unchanged.
// Five ~1 s fields bypass video/OSD: red, green, blue, white, black. Afterwards
// retain live video and OSD, with colour bars only when video pixels are absent.
module a741_display_diagnostic #(
    parameter CLOCK_HZ=50000000, FRAMES_PER_COLOR=34, WIDTH=480
)(
    input wire clk,rst_n,frame_blank,input wire [10:0] x,
    input wire [15:0] pixel,osd_rgb,input wire pixel_valid,
    input wire locked,ddr_ready,camera_ready,camera_error,phy_ready,phy_error,
    output wire [15:0] overlay_pixel,output wire overlay_pixel_valid,
    output reg [15:0] panel_rgb,output wire [7:0] led
);
    localparam HB_BITS=$clog2(CLOCK_HZ/2)>0 ? $clog2(CLOCK_HZ/2):1;
    localparam COLOR_BITS=$clog2(FRAMES_PER_COLOR)>0 ? $clog2(FRAMES_PER_COLOR):1;
    reg [HB_BITS-1:0] heartbeat_count;
    reg heartbeat;
    reg [4:0] frame_count;
    reg [COLOR_BITS-1:0] color_frames;
    reg [2:0] stage;
    reg [15:0] bars;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            heartbeat_count<=0;heartbeat<=0;frame_count<=0;color_frames<=0;stage<=0;
        end else begin
            if(heartbeat_count==CLOCK_HZ/2-1) begin heartbeat_count<=0;heartbeat<=!heartbeat;end
            else heartbeat_count<=heartbeat_count+1'b1;
            if(frame_blank) begin
                frame_count<=frame_count+1'b1;
                if(stage<5) begin
                    if(color_frames==FRAMES_PER_COLOR-1) begin color_frames<=0;stage<=stage+1'b1;end
                    else color_frames<=color_frames+1'b1;
                end
            end
        end
    always @* begin
        if(x<WIDTH/8) bars=16'hffff;
        else if(x<WIDTH*2/8) bars=16'hffe0;
        else if(x<WIDTH*3/8) bars=16'h07ff;
        else if(x<WIDTH*4/8) bars=16'h07e0;
        else if(x<WIDTH*5/8) bars=16'hf81f;
        else if(x<WIDTH*6/8) bars=16'hf800;
        else if(x<WIDTH*7/8) bars=16'h001f;
        else bars=16'h0000;
        case(stage)
            0:panel_rgb=16'hf800;
            1:panel_rgb=16'h07e0;
            2:panel_rgb=16'h001f;
            3:panel_rgb=16'hffff;
            4:panel_rgb=16'h0000;
            default:panel_rgb=osd_rgb;
        endcase
    end
    assign overlay_pixel=pixel_valid ? pixel:bars;
    assign overlay_pixel_valid=1'b1;
    // D1: system activity, D2: 16-frame toggle (~0.48 s), D5/D7: latched
    // initialization errors, not motor faults. These are internal activity
    // indicators, not measurements of the electrical LCD connector signals.
    assign led={phy_error,phy_ready,camera_error,camera_ready,ddr_ready,frame_count[4],heartbeat,locked};
endmodule
`default_nettype wire
