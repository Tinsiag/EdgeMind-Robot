`timescale 1ns/1ps
`default_nettype none
// AT043TN24 on the existing J1 RGB565 interface. All logic uses sys_clk.
// Fixed /5 of the 50 MHz board clock: 10 MHz PCLK, 40 ns high / 60 ns low.
// AT043TN24 permits 5..12 MHz and requires each pulse to be at least 26.7 ns.
// RGB/DE/HS/VS update only on PCLK falling transitions; the panel samples rising.
// Eleven complete 15.015 ms frames exceed the datasheet's 160 ms LED delay.
module a741_tft480_panel #(parameter integer BACKLIGHT_FRAMES=11)(
    input wire clk,rst_n,input wire [895:0] snapshot,input wire [255:0] fusion_snapshot,
    output reg tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl,
    output reg [15:0] tft_rgb
);
    localparam STARTUP_BITS=BACKLIGHT_FRAMES>0 ? $clog2(BACKLIGHT_FRAMES+1):1;
    // The vendor's inclusive sync endpoints give 41 clocks / 10 lines.
    // Keep the datasheet's two-clock / two-line back porches: the AC620 demo
    // starts DE at 42,11, leaving only one of each after those sync pulses.
    localparam H_SYNC=41,H_BEGIN=43,H_END=523,H_LAST=524;
    localparam V_SYNC=10,V_BEGIN=12,V_END=284,V_LAST=285;
    reg [2:0] phase;
    reg [9:0] h;
    reg [8:0] v;
    reg [STARTUP_BITS-1:0] startup_frames;
    wire falling=phase==4;
    wire active=h>=H_BEGIN && h<H_END && v>=V_BEGIN && v<V_END;
    wire [10:0] x={1'b0,h}-11'(H_BEGIN),y={2'd0,v}-11'(V_BEGIN);
    wire frame_blank=falling && h==0 && v==V_END;
    // Wrap each existing 64-character OSD line into two 32-character rows.
    // This retains the original 12x16 font at a readable size on the 4.3 inch LCD.
    wire content=active && x>=48 && x<432 && y>=64 && y<256;
    wire [7:0] text_y=8'(y-64);
    wire [10:0] osd_x=content ? x-48+(text_y[4] ? 384:0):11'd1800;
    wire [10:0] osd_y={4'd0,text_y[7:5],text_y[3:0]};
    wire [15:0] osd_rgb;
    a741_osd #(.FUSION_ENABLED(1),.PANEL_LAYOUT(1)) osd(.clk(clk),.rst_n(rst_n),.frame_blank(frame_blank),
        .de(content),.x(osd_x),.y(osd_y),.pixel(16'd0),.pixel_valid(1'b0),
        .status_snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.status_update(1'b1),.rgb(osd_rgb));

    function [34:0] font;
        input [7:0] c;
        begin case(c)
            "0":font=35'b01110_10001_10011_10101_11001_10001_01110;
            "1":font=35'b00100_01100_00100_00100_00100_00100_01110;
            "2":font=35'b01110_10001_00001_00010_00100_01000_11111;
            "3":font=35'b11110_00001_00001_01110_00001_00001_11110;
            "4":font=35'b00010_00110_01010_10010_11111_00010_00010;
            "5":font=35'b11111_10000_10000_11110_00001_00001_11110;
            "6":font=35'b01110_10000_10000_11110_10001_10001_01110;
            "7":font=35'b11111_00001_00010_00100_01000_01000_01000;
            "8":font=35'b01110_10001_10001_01110_10001_10001_01110;
            "9":font=35'b01110_10001_10001_01111_00001_00001_01110;
            "A":font=35'b01110_10001_10001_11111_10001_10001_10001;
            "B":font=35'b11110_10001_10001_11110_10001_10001_11110;
            "C":font=35'b01111_10000_10000_10000_10000_10000_01111;
            "D":font=35'b11110_10001_10001_10001_10001_10001_11110;
            "E":font=35'b11111_10000_10000_11110_10000_10000_11111;
            "F":font=35'b11111_10000_10000_11110_10000_10000_10000;
            "I":font=35'b01110_00100_00100_00100_00100_00100_01110;
            "K":font=35'b10001_10010_10100_11000_10100_10010_10001;
            "L":font=35'b10000_10000_10000_10000_10000_10000_11111;
            "M":font=35'b10001_11011_10101_10101_10001_10001_10001;
            "O":font=35'b01110_10001_10001_10001_10001_10001_01110;
            "P":font=35'b11110_10001_10001_11110_10000_10000_10000;
            "Q":font=35'b01110_10001_10001_10001_10101_10010_01101;
            "R":font=35'b11110_10001_10001_11110_10100_10010_10001;
            "S":font=35'b01111_10000_10000_01110_00001_00001_11110;
            "T":font=35'b11111_00100_00100_00100_00100_00100_00100;
            "G":font=35'b01110_10001_10000_10111_10001_10001_01110;
            "H":font=35'b10001_10001_10001_11111_10001_10001_10001;
            "N":font=35'b10001_11001_10101_10011_10001_10001_10001;
            "U":font=35'b10001_10001_10001_10001_10001_10001_01110;
            "V":font=35'b10001_10001_10001_10001_10001_01010_00100;
            "W":font=35'b10001_10001_10001_10101_10101_11011_10001;
            "X":font=35'b10001_10001_01010_00100_01010_10001_10001;
            "Y":font=35'b10001_10001_01010_00100_00100_00100_00100;
            "-":font=35'b00000_00000_00000_11111_00000_00000_00000;
            "/":font=35'b00001_00010_00100_01000_10000_00000_00000;
            ":":font=35'b00000_00100_00100_00000_00100_00100_00000;
            default:font=0;
        endcase end
    endfunction
    wire [127:0] title="EDGEMIND  NAV   ";
    wire title_area=active && y>=24 && y<40 && x>=144 && x<336;
    // Only the 192-pixel title window uses these values. Bound the operand
    // before division so synthesis does not build 32-bit /12 and %12 logic.
    wire [7:0] title_x=x[7:0]-8'd144;
    wire [3:0] title_y=y[3:0]-4'd8;
    wire [3:0] title_index=4'(title_x/8'd12);
    wire [2:0] title_col=3'((title_x%8'd12)>>1),title_row=title_y[3:1];
    wire [7:0] title_ch=title[127-title_index*8-:8];
    wire [34:0] title_glyph=font(title_ch);
    wire title_pixel=title_area && title_col<5 && title_row<7 && title_glyph[34-title_row*5-title_col];
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            phase<=0;tft_clk<=0;h<=0;v<=0;startup_frames<=0;
            tft_de<=0;tft_hsync<=1;tft_vsync<=1;tft_bl<=0;tft_rgb<=0;
        end else begin
            phase<=falling ? 3'd0:phase+3'd1;
            if(phase==2) tft_clk<=1;
            if(falling) tft_clk<=0;
            if(falling) begin
                tft_hsync<=h>=H_SYNC;tft_vsync<=v>=V_SYNC;tft_de<=active;
                tft_rgb<=!active ? 16'd0:content ? osd_rgb:title_pixel ? 16'hffff:
                         y<52 ? 16'h0188:16'h0841;
                // Switch on at the first blank pixel after complete startup frames.
                if(h==0 && v==0 && startup_frames>=BACKLIGHT_FRAMES) tft_bl<=1;
                if(h==H_LAST) begin
                    h<=0;
                    if(v==V_LAST) begin
                        v<=0;
                        if(startup_frames<BACKLIGHT_FRAMES) startup_frames<=startup_frames+1'b1;
                    end else v<=v+1'b1;
                end else h<=h+1'b1;
            end
        end
endmodule
`default_nettype wire
