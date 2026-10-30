`timescale 1ns/1ps
`default_nettype none
// Two inset HUD bars inside the observed 480x272 visible window. 2x glyphs,
// explicit margins and frame-coherent status colors; live video outside bars.
// No HDMI layout, maps, positions, goals, waypoint counters or video mailbox.
module a745_osd #(parameter WIDTH=800,HEIGHT=480,PIPELINED=0)(
 input wire clk,rst_n,frame_blank,de,input wire [10:0] x,y,
 input wire [15:0] pixel,input wire pixel_valid,
 input wire [895:0] status_snapshot,input wire status_update,
 input wire [255:0] fusion_snapshot,output reg [15:0] rgb
);
 reg [895:0] pending,working;reg [255:0] fusion_pending,fusion_working;
 reg pending_valid;
 reg [255:0] lines[0:3],work_lines[0:3];
 localparam IDLE=0,BUILD=1,LOAD=2,CONVERT=3,STORE=4,READY=5,SAMPLE=6;
 reg [2:0] state,field;
 reg [4:0] bit_count;reg [16:0] binary;reg [19:0] bcd;
 reg negative;reg signed [31:0] field_value,field_sample;reg [31:0] magnitude;
 reg [19:0] adjusted_bcd;reg [47:0] ascii_value,angle_value;
 integer n,digit;
 function [7:0] hex_digit(input [3:0] v);
  begin hex_digit=v<10 ? 8'd48+v:8'd55+v;end
 endfunction
 function signed [31:0] angle_tenths;
  input signed [15:0] value;reg [15:0] absolute_value;reg [26:0] product;
  begin absolute_value=value[15] ? -value:value;product=absolute_value*11'd1800;
   angle_tenths=value[15] ? -$signed({20'd0,product[26:15]}):$signed({20'd0,product[26:15]});end
 endfunction
 function [8:0] cell_position;
  input [10:0] coordinate;reg [8:0] remainder;reg [5:0] quotient;
  begin remainder=coordinate[9:1];quotient=0;
   if(remainder>=192) begin remainder=remainder-9'd192;quotient[5]=1;end
   if(remainder>=96) begin remainder=remainder-9'd96;quotient[4]=1;end
   if(remainder>=48) begin remainder=remainder-9'd48;quotient[3]=1;end
   if(remainder>=24) begin remainder=remainder-9'd24;quotient[2]=1;end
   if(remainder>=12) begin remainder=remainder-9'd12;quotient[1]=1;end
   if(remainder>=6) begin remainder=remainder-9'd6;quotient[0]=1;end
   cell_position={quotient,remainder[2:0]};end
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
            ".":font=35'b00000_00000_00000_00000_00000_00100_00100;
            default:font=0;
        endcase end
    endfunction

 function [7:0] read_character;
  input [1:0] selected_row;input [4:0] selected_character;
  begin case(selected_row)
   0:read_character=lines[0][255-{selected_character,3'b000}-:8];
   1:read_character=lines[1][255-{selected_character,3'b000}-:8];
   2:read_character=lines[2][255-{selected_character,3'b000}-:8];
   3:read_character=lines[3][255-{selected_character,3'b000}-:8];
  endcase end
 endfunction
 function [255:0] field_mask;
  input integer row;
  begin field_mask=0;case(row)
   1:begin field_mask[255-2*8-:48]={48{1'b1}};field_mask[255-11*8-:48]={48{1'b1}};field_mask[255-20*8-:48]={48{1'b1}};end
   2:begin field_mask[255-2*8-:48]={48{1'b1}};field_mask[255-11*8-:48]={48{1'b1}};field_mask[255-20*8-:48]={48{1'b1}};end
  endcase end
  endfunction
 always @* begin
  case(field)
   0:field_value=angle_tenths(fusion_working[47:32]);
   1:field_value=angle_tenths(fusion_working[63:48]);
   2:field_value=angle_tenths(working[431:416]);
   3:field_value={16'd0,working[479:464]};
   4:field_value={16'd0,working[495:480]};
   5:field_value={16'd0,working[511:496]};
   default:field_value={16'd0,working[207:192]};
  endcase
  magnitude=field_sample[31] ? -field_sample:field_sample;
  adjusted_bcd=bcd;
  for(digit=0;digit<5;digit=digit+1)
   if(bcd[digit*4+:4]>=5) adjusted_bcd[digit*4+:4]=bcd[digit*4+:4]+4'd3;
  ascii_value={negative ? 8'h2d:8'h20,8'd48+{4'd0,bcd[19:16]},8'd48+{4'd0,bcd[15:12]},
   8'd48+{4'd0,bcd[11:8]},8'd48+{4'd0,bcd[7:4]},8'd48+{4'd0,bcd[3:0]}};
  angle_value={negative ? 8'h2d:8'h20,8'd48+{4'd0,bcd[15:12]},8'd48+{4'd0,bcd[11:8]},
   8'd48+{4'd0,bcd[7:4]},8'h2e,8'd48+{4'd0,bcd[3:0]}};
 end
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin
   pending<=0;working<=0;fusion_pending<=0;fusion_working<=0;pending_valid<=0;
   state<=IDLE;field<=0;bit_count<=0;binary<=0;bcd<=0;negative<=0;field_sample<=0;
   for(n=0;n<4;n=n+1) lines[n]<={32{8'h20}};
  end else begin
   if(status_update) begin pending<=status_snapshot;fusion_pending<=fusion_snapshot;pending_valid<=1;end
   case(state)
    IDLE:if(pending_valid) begin working<=pending;fusion_working<=fusion_pending;state<=BUILD;
     if(!status_update) pending_valid<=0;end
    BUILD:begin field<=0;state<=LOAD;end
    LOAD:begin field_sample<=field_value;state<=SAMPLE;end
    SAMPLE:begin binary<=magnitude>99999 ? 17'd99999:magnitude[16:0];
     negative<=field_sample[31];bcd<=0;bit_count<=0;state<=CONVERT;end
    CONVERT:begin bcd<={adjusted_bcd[18:0],binary[16]};binary<={binary[15:0],1'b0};
     if(bit_count==16) state<=STORE;else bit_count<=bit_count+1'b1;end
    STORE:if(field==5) state<=READY;else begin field<=field+1'b1;state<=LOAD;end
    READY:if(frame_blank) begin for(n=0;n<4;n=n+1) lines[n]<=work_lines[n];state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 // Staging data has no reset tree or redundant clearing of numeric fields.
 // BUILD+all seven STORE operations must finish before READY publishes it.
 always @(posedge clk) if(rst_n) case(state)
  BUILD:begin
   for(n=0;n<4;n=n+1) work_lines[n]<=(work_lines[n]&field_mask(n))|({32{8'h20}}&~field_mask(n));
   work_lines[0]<="A745 ARM:OFF IMU:WAIT CAM:WAIT  ";
   work_lines[1]<="R:       P:       Y:       DEG  ";
   work_lines[2]<="F:       L:       R:       MM   ";
   work_lines[3]<="MODE:       NET:WAIT ERR:0000   ";
   work_lines[0][255-9*8-:24]<=working[165] ? "ON ":"OFF";
   work_lines[0][255-17*8-:32]<=working[160] && working[161] ? "OK  ":"WAIT";
   work_lines[0][255-26*8-:32]<=working[798:795]==11 ? "OK  ":"WAIT";
   work_lines[3][255-16*8-:32]<=working[173] ? "OK  ":"WAIT";
   case(working[183:176])
    0:work_lines[3][255-5*8-:48]<="IDLE  ";
    1:work_lines[3][255-5*8-:48]<="CALIB ";
    2:work_lines[3][255-5*8-:48]<="CRUISE";
    3:work_lines[3][255-5*8-:48]<="LEFT  ";
    4:work_lines[3][255-5*8-:48]<="RIGHT ";
    5:work_lines[3][255-5*8-:48]<="BLOCK ";
    8:work_lines[3][255-5*8-:48]<="FAULT ";
    9:work_lines[3][255-5*8-:48]<="SETTLE";
    default:work_lines[3][255-5*8-:48]<="WAIT  ";
   endcase
   work_lines[3][255-25*8-:8]<=hex_digit(working[207:204]);
   work_lines[3][255-26*8-:8]<=hex_digit(working[203:200]);
   work_lines[3][255-27*8-:8]<=hex_digit(working[199:196]);
   work_lines[3][255-28*8-:8]<=hex_digit(working[195:192]);
   if(working[791:784]!=0 || working[170]) begin
    work_lines[3]<="CAM:00 REG:0000 READ:00 F:0000  ";
   work_lines[3][255-4*8-:8]<=hex_digit(working[791:788]);
   work_lines[3][255-5*8-:8]<=hex_digit(working[787:784]);
   work_lines[3][255-11*8-:8]<=hex_digit(working[575:572]);
   work_lines[3][255-12*8-:8]<=hex_digit(working[571:568]);
   work_lines[3][255-13*8-:8]<=hex_digit(working[567:564]);
   work_lines[3][255-14*8-:8]<=hex_digit(working[563:560]);
   work_lines[3][255-21*8-:8]<=hex_digit(working[551:548]);
   work_lines[3][255-22*8-:8]<=hex_digit(working[547:544]);
   work_lines[3][255-26*8-:8]<=hex_digit(working[207:204]);
   work_lines[3][255-27*8-:8]<=hex_digit(working[203:200]);
   work_lines[3][255-28*8-:8]<=hex_digit(working[199:196]);
   work_lines[3][255-29*8-:8]<=hex_digit(working[195:192]);
   end
  end
  STORE:case(field)
   0:work_lines[1][255-2*8-:48]<=fusion_working[64] ? angle_value:" WAIT ";
   1:work_lines[1][255-11*8-:48]<=fusion_working[64] ? angle_value:" WAIT ";
   2:work_lines[1][255-20*8-:48]<=working[160] ? angle_value:" WAIT ";
   3:work_lines[2][255-2*8-:48]<=working[163] && working[479:464]!=65535 ? ascii_value:" WAIT ";
   4:work_lines[2][255-11*8-:48]<=working[163] && working[495:480]!=65535 ? ascii_value:" WAIT ";
   5:work_lines[2][255-20*8-:48]<=working[163] && working[511:496]!=65535 ? ascii_value:" WAIT ";
  endcase
 endcase
 reg [8:0] cell_q;reg [1:0] row_q;reg [2:0] gy_q,col_q,gy_qq;
 reg active_q,active_qq;reg [7:0] ch_q;reg [34:0] glyph;reg [5:0] glyph_index;
 localparam VIEW_WIDTH=480,VIEW_HEIGHT=272,TEXT_LEFT=32;
 wire card_x=x>=16 && x<VIEW_WIDTH-16;
 wire card_top=y>=12 && y<68;wire card_bottom=y>=VIEW_HEIGHT-68 && y<VIEW_HEIGHT-12;
 wire card=de && card_x && (card_top || card_bottom);
 wire border=card && (x<18 || x>=VIEW_WIDTH-18 || (card_top && (y<14 || y>=66)) || (card_bottom && (y<VIEW_HEIGHT-66 || y>=VIEW_HEIGHT-14)));
 reg card_q,card_qq,border_q,border_qq;reg health_fault,health_wait;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin health_fault<=0;health_wait<=1;end
  else if(state==READY && frame_blank) begin
   health_fault<=working[207:192]!=0 || working[170] || working[171] || working[172] || working[174];
   health_wait<=!working[160] || !working[168] || !working[169];
  end
 wire top_text=y>=24 && y<56;wire bottom_text=y>=VIEW_HEIGHT-56 && y<VIEW_HEIGHT-24;
 wire [10:0] text_y=top_text ? y-11'd24:y-11'(VIEW_HEIGHT-88);
 reg [15:0] pixel_q,pixel_qq;reg valid_q,valid_qq,de_q,de_qq;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin pixel_q<=0;pixel_qq<=0;valid_q<=0;valid_qq<=0;de_q<=0;de_qq<=0;card_q<=0;card_qq<=0;border_q<=0;border_qq<=0;end
  else begin pixel_q<=pixel;pixel_qq<=pixel_q;valid_q<=pixel_valid;valid_qq<=valid_q;de_q<=de;de_qq<=de_q;card_q<=card;card_qq<=card_q;border_q<=border;border_qq<=border_q;end
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin cell_q<=0;row_q<=0;gy_q<=0;col_q<=0;gy_qq<=0;active_q<=0;active_qq<=0;ch_q<=32;end
  else begin
   cell_q<=cell_position(x-11'(TEXT_LEFT));row_q<=text_y[5:4];gy_q<=text_y[3:1];
   active_q<=de && x>=TEXT_LEFT && x<TEXT_LEFT+384 && (top_text || bottom_text);
   ch_q<=active_q ? read_character(row_q,cell_q[7:3]):8'd32;
   col_q<=cell_q[2:0];gy_qq<=gy_q;active_qq<=active_q;
  end
 always @* begin
  rgb=PIPELINED ? (de_qq ? (valid_qq ? pixel_qq:16'h2104):16'd0):
                 (de ? (pixel_valid ? pixel:16'h2104):16'd0);
  glyph=font(ch_q);glyph_index=6'd34-({3'd0,gy_qq}*6'd5)-{3'd0,col_q};
  if(card_qq) rgb=border_qq ? (health_fault ? 16'hf980:16'h1b4c):16'h08a4;
  if(active_qq && col_q<5 && gy_qq<7 && glyph[glyph_index])
   rgb=row_q==0 ? (health_fault ? 16'hfb88:health_wait ? 16'hfd60:16'h47b9):row_q==3 ? (health_fault ? 16'hfb88:16'hbdf7):16'hffff;
 end
endmodule
`default_nettype wire
