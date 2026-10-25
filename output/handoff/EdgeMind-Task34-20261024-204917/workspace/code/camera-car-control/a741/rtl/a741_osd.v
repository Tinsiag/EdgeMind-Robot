`timescale 1ns/1ps
`default_nettype none
module a741_osd(
    input wire clk,rst_n,frame_blank,de,input wire [10:0] x,y,
    input wire [15:0] pixel,input wire pixel_valid,
    input wire [895:0] status_snapshot,input wire status_update,
    output reg [15:0] rgb
);
    reg [895:0] pending,working;
    reg pending_valid;
    reg [511:0] lines[0:3],work_lines[0:3];
    localparam IDLE=0,BUILD=1,LOAD=2,CONVERT=3,STORE=4,READY=5;
    reg [2:0] state;
    reg [3:0] field;
    reg [4:0] bit_count;
    reg [16:0] binary;
    reg [19:0] bcd;
    reg negative;
    reg signed [31:0] field_value;
    reg [31:0] magnitude;
    reg [19:0] adjusted_bcd;
    reg [47:0] ascii_value;
    reg [8:0] pixel_cell;
    reg [5:0] char_index;
    reg [2:0] col,gy;
    reg [1:0] row;
    reg [5:0] glyph_index;
    integer n,digit;
    reg [7:0] ch;reg [34:0] glyph;
    function signed [31:0] scaled_angle;
        input signed [15:0] value;
        input [10:0] scale;
        reg [15:0] absolute_value;
        reg [26:0] product;
        begin
            absolute_value=value[15] ? -value:value;
            product=absolute_value*scale;
            scaled_angle=value[15] ? -$signed({20'd0,product[26:15]}):$signed({20'd0,product[26:15]});
        end
    endfunction
    function [8:0] cell_position;
        input [10:0] coordinate;
        reg [8:0] remainder;
        reg [5:0] quotient;
        begin
            remainder=coordinate[9:1];quotient=0;
            if(remainder>=192) begin remainder=remainder-9'd192;quotient[5]=1;end
            if(remainder>=96) begin remainder=remainder-9'd96;quotient[4]=1;end
            if(remainder>=48) begin remainder=remainder-9'd48;quotient[3]=1;end
            if(remainder>=24) begin remainder=remainder-9'd24;quotient[2]=1;end
            if(remainder>=12) begin remainder=remainder-9'd12;quotient[1]=1;end
            if(remainder>=6) begin remainder=remainder-9'd6;quotient[0]=1;end
            cell_position={quotient,remainder[2:0]};
        end
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
            "G":font=35'b01110_10001_10000_10111_10001_10001_01110;
            "H":font=35'b10001_10001_10001_11111_10001_10001_10001;
            "N":font=35'b10001_11001_10101_10011_10001_10001_10001;
            "U":font=35'b10001_10001_10001_10001_10001_10001_01110;
            "V":font=35'b10001_10001_10001_10001_10001_01010_00100;
            "W":font=35'b10001_10001_10001_10101_10101_11011_10001;
            "Y":font=35'b10001_10001_01010_00100_00100_00100_00100;
            "-":font=35'b00000_00000_00000_11111_00000_00000_00000;
            "/":font=35'b00001_00010_00100_01000_10000_00000_00000;
            ":":font=35'b00000_00100_00100_00000_00100_00100_00000;
            default:font=0;
        endcase end
    endfunction

    always @* begin
        case(field)
            0:field_value={16'd0,working[207:192]};
            1:field_value=working[255:224];
            2:field_value=working[319:288];
            3:field_value=working[287:256];
            4:field_value=working[351:320];
            5:field_value=scaled_angle(working[431:416],11'd180);
            6:field_value={16'd0,working[463:448]};
            7:field_value=scaled_angle(working[447:432],11'd2000);
            8:field_value={16'd0,working[479:464]};
            9:field_value={16'd0,working[495:480]};
            10:field_value={16'd0,working[511:496]};
            default:field_value=working[159:128];
        endcase
        magnitude=field_value[31] ? -field_value:field_value;
        adjusted_bcd=bcd;
        for(digit=0;digit<5;digit=digit+1)
            if(bcd[digit*4+:4]>=5) adjusted_bcd[digit*4+:4]=bcd[digit*4+:4]+4'd3;
        ascii_value={negative ? 8'h2d:8'h20,8'd48+{4'd0,bcd[19:16]},8'd48+{4'd0,bcd[15:12]},
            8'd48+{4'd0,bcd[11:8]},8'd48+{4'd0,bcd[7:4]},8'd48+{4'd0,bcd[3:0]}};
    end

    // One shared double-dabble converter prepares a coherent text frame off-screen.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            pending<=0;working<=0;pending_valid<=0;state<=IDLE;field<=0;
            bit_count<=0;binary<=0;bcd<=0;negative<=0;
            for(n=0;n<4;n=n+1) begin lines[n]<={64{8'h20}};work_lines[n]<={64{8'h20}};end
        end else begin
            if(status_update) begin pending<=status_snapshot;pending_valid<=1;end
            case(state)
                IDLE:if(pending_valid) begin
                    working<=pending;state<=BUILD;
                    if(!status_update) pending_valid<=0;
                end
                BUILD:begin
                    for(n=0;n<4;n=n+1) work_lines[n]<={64{8'h20}};
                    work_lines[0][511-:48]<="MODE: ";
                    case(working[183:176])
                        0:work_lines[0][463-:64]<="DISARM  ";
                        1:work_lines[0][463-:64]<="ARMED   ";
                        2:work_lines[0][463-:64]<="DRIVE   ";
                        3:work_lines[0][463-:64]<="FAULT   ";
                        4:work_lines[0][463-:64]<="ROTATE  ";
                        default:work_lines[0][463-:64]<="INVALID ";
                    endcase
                    work_lines[0][391-:48]<="STOP: ";
                    work_lines[0][343-:48]<=working[192] ? "TTL   ":
                        working[194] ? "ENC   ":working[196] ? "IMU   ":working[197] ? "TOF   ":working[201] ? "TURN  ":"NONE  ";
                    work_lines[0][287-:40]<="DDR: ";
                    work_lines[0][247-:48]<=working[168] ? "READY ":"WAIT  ";
                    work_lines[0][191-:48]<="FAULT ";
                    work_lines[0][95-:32]<="CAM:";
                    work_lines[0][63-:48]<=working[169] ? "READY ":"INVAL ";
                    work_lines[1][511-:32]<="LT: ";work_lines[1][431-:32]<=" LM:";
                    work_lines[1][343-:32]<="RT: ";work_lines[1][263-:32]<=" RM:";
                    work_lines[1][175-:32]<="MM/S";
                    work_lines[2][511-:40]<="YAW: ";work_lines[2][423-:32]<=" DEG";
                    work_lines[2][383-:40]<="TOF: ";work_lines[2][295-:24]<=" MM";
                    work_lines[2][263-:40]<="GYRO ";work_lines[2][175-:40]<="DEG/S";
                    work_lines[3][511-:64]<="LIDAR F:";work_lines[3][399-:24]<=" L:";
                    work_lines[3][327-:24]<=" R:";work_lines[3][247-:16]<="MM";
                    work_lines[3][223-:40]<=" CFG:";field<=0;state<=LOAD;
                end
                LOAD:begin
                    binary<=magnitude>99999 ? 17'd99999:magnitude[16:0];
                    negative<=field_value[31];bcd<=0;bit_count<=0;state<=CONVERT;
                end
                CONVERT:begin
                    bcd<={adjusted_bcd[18:0],binary[16]};binary<={binary[15:0],1'b0};
                    if(bit_count==16) state<=STORE;else bit_count<=bit_count+1'b1;
                end
                STORE:begin
                    case(field)
                        0:work_lines[0][143-:48]<=ascii_value;
                        1:work_lines[1][479-:48]<=ascii_value;
                        2:work_lines[1][399-:48]<=ascii_value;
                        3:work_lines[1][311-:48]<=ascii_value;
                        4:work_lines[1][231-:48]<=ascii_value;
                        5:work_lines[2][471-:48]<=working[160] ? ascii_value:"STALE ";
                        6:work_lines[2][343-:48]<=working[162] ? ascii_value:"STALE ";
                        7:work_lines[2][223-:48]<=working[161] ? ascii_value:"STALE ";
                        8:work_lines[3][447-:48]<=working[163] && working[479:464]!=65535 ? ascii_value:"INVAL ";
                        9:work_lines[3][375-:48]<=working[163] && working[495:480]!=65535 ? ascii_value:"INVAL ";
                        10:work_lines[3][303-:48]<=working[163] && working[511:496]!=65535 ? ascii_value:"INVAL ";
                        11:work_lines[3][183-:48]<=ascii_value;
                    endcase
                    if(field==11) state<=READY;else begin field<=field+1'b1;state<=LOAD;end
                end
                READY:if(frame_blank) begin
                    for(n=0;n<4;n=n+1) lines[n]<=work_lines[n];
                    state<=IDLE;
                end
                default:state<=IDLE;
            endcase
        end
    always @* begin
        rgb=de ? (pixel_valid ? pixel:16'h2104):16'd0;
        pixel_cell=cell_position(x);char_index=pixel_cell[8:3];col=pixel_cell[2:0];row=y[5:4];gy=y[3:1];
        glyph_index=6'd34-({3'd0,gy}*6'd5)-{3'd0,col};ch=" ";glyph=0;
        if(de && y<64 && x<768) begin
            rgb=16'h0022;ch=lines[row][511-{char_index,3'b000}-:8];glyph=font(ch);
            if(col<5 && gy<7 && glyph[glyph_index]) rgb=16'hffff;
        end
    end
endmodule
`default_nettype wire
