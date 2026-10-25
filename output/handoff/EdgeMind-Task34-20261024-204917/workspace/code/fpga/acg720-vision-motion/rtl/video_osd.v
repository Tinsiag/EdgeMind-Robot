`timescale 1ns/1ps
`default_nettype none
// Hex telemetry is labelled on screen: MODE, DIST, LSPD, RSPD, STOP.
module video_osd(
    input wire clk,rst_n,frame_blank,de,input wire [10:0] x,y,
    input wire [15:0] camera_pixel,input wire camera_valid,
    input wire [191:0] status_snapshot,input wire status_update,
    output reg [15:0] rgb
);
    reg [191:0] pending,snapshot;
    wire [10:0] near_center=snapshot[10:0],far_center=snapshot[21:11];
    wire [10:0] ny0=snapshot[32:22],ny1=snapshot[43:33],fy0=snapshot[54:44],fy1=snapshot[65:55];
    integer column,row,char_cell;reg [7:0] ch;reg [34:0] glyph;reg on;
    function [7:0] hexchar;
        input [3:0] n;
        begin hexchar=n<10 ? 8'd48+n:8'd65+n-10;end
    endfunction
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
            "L":font=35'b10000_10000_10000_10000_10000_10000_11111;
            "M":font=35'b10001_11011_10101_10101_10001_10001_10001;
            "O":font=35'b01110_10001_10001_10001_10001_10001_01110;
            "P":font=35'b11110_10001_10001_11110_10000_10000_10000;
            "R":font=35'b11110_10001_10001_11110_10100_10010_10001;
            "S":font=35'b01111_10000_10000_01110_00001_00001_11110;
            "T":font=35'b11111_00100_00100_00100_00100_00100_00100;
            default:font=0;
        endcase end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin pending<=0;snapshot<=0;end
        else begin if(status_update) pending<=status_snapshot;if(frame_blank) snapshot<=pending;end
    always @* begin
        rgb=de ? (camera_valid ? camera_pixel:16'h780f):16'd0;
        column=0;row=0;char_cell=0;ch=" ";glyph=0;on=0;
        if(de && ((y==ny0 || y==ny1 || y==fy0 || y==fy1) || x==400)) rgb=16'h07e0;
        if(de && ((y>=ny0 && y<=ny1 && x==near_center)||(y>=fy0 && y<=fy1 && x==far_center))) rgb=16'hf800;
        if(de && y<32) begin
            rgb=16'h0008;char_cell=x/12;column=(x%12)/2;row=y/4;
            case(char_cell)
                0:ch="M";1:ch="O";2:ch="D";3:ch="E";
                5:ch=hexchar({3'd0,snapshot[66]});
                8:ch="D";9:ch="I";10:ch="S";11:ch="T";
                13:ch=hexchar(snapshot[82:79]);14:ch=hexchar(snapshot[78:75]);15:ch=hexchar(snapshot[74:71]);16:ch=hexchar(snapshot[70:67]);
                19:ch="L";20:ch="S";21:ch="P";22:ch="D";
                24:ch=hexchar(snapshot[98:95]);25:ch=hexchar(snapshot[94:91]);26:ch=hexchar(snapshot[90:87]);27:ch=hexchar(snapshot[86:83]);
                30:ch="R";31:ch="S";32:ch="P";33:ch="D";
                35:ch=hexchar(snapshot[114:111]);36:ch=hexchar(snapshot[110:107]);37:ch=hexchar(snapshot[106:103]);38:ch=hexchar(snapshot[102:99]);
                41:ch="S";42:ch="T";43:ch="O";44:ch="P";
                46:ch=hexchar(snapshot[122:119]);47:ch=hexchar(snapshot[118:115]);
                50:ch="S";51:ch="T";52:ch="A";53:ch="T";54:ch="E";
                56:ch=hexchar(snapshot[130:127]);57:ch=hexchar(snapshot[126:123]);
                default:ch=" ";
            endcase
            glyph=font(ch);
            if(column<5 && row<7) on=glyph[34-row*5-column];
            if(on) rgb=16'hffff;
        end
    end
endmodule
`default_nettype wire
