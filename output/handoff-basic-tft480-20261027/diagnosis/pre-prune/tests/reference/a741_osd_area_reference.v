// Frozen pre-area-optimization implementation, 2026-10-27.
// Simulation oracle only; never added to hardware synthesis sources.
`timescale 1ns/1ps
`default_nettype none
module a741_osd_area_reference #(parameter FUSION_ENABLED=0,PANEL_LAYOUT=0)(
    input wire clk,rst_n,frame_blank,de,input wire [10:0] x,y,
    input wire [15:0] pixel,input wire pixel_valid,
    input wire [895:0] status_snapshot,input wire status_update,
    input wire [255:0] fusion_snapshot,
    output reg [15:0] rgb
);
    reg [895:0] pending,working;
    reg pending_valid;
    reg [511:0] lines[0:5],work_lines[0:5];
    reg [255:0] fusion_pending,fusion_working;
    localparam IDLE=0,BUILD=1,LOAD=2,CONVERT=3,STORE=4,READY=5,SAMPLE=6;
    reg [2:0] state;
    reg [4:0] field;
    reg [4:0] bit_count;
    reg [16:0] binary;
    reg [19:0] bcd;
    reg negative;
    reg signed [31:0] field_value;
    reg signed [31:0] field_sample;
    reg [31:0] magnitude;
    reg [19:0] adjusted_bcd;
    reg [47:0] ascii_value;
    reg [8:0] pixel_cell;
    reg [5:0] char_index;
    reg [2:0] col,gy;
    reg [2:0] row;
    reg [5:0] glyph_index;
    integer n,digit;
    reg [7:0] ch;reg [34:0] glyph;
    reg [8:0] panel_cell;
    reg [2:0] panel_row,panel_gy;
    reg panel_active;
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
            8:field_value={16'd0,FUSION_ENABLED!=0 ? fusion_working[127:112]:working[479:464]};
            9:field_value={16'd0,working[495:480]};
            10:field_value={16'd0,working[511:496]};
            11:field_value=working[159:128];
            12:field_value=fusion_working[63:32];
            13:field_value=fusion_working[95:64];
            14:field_value={24'd0,fusion_working[15:8]};
            15:field_value={24'd0,fusion_working[23:16]};
            16:field_value={24'd0,fusion_working[167:160]};
            17:field_value={24'd0,fusion_working[175:168]}+{31'd0,fusion_working[200]};
            default:field_value={24'd0,fusion_working[183:176]};
        endcase
        magnitude=field_sample[31] ? -field_sample:field_sample;
        adjusted_bcd=bcd;
        for(digit=0;digit<5;digit=digit+1)
            if(bcd[digit*4+:4]>=5) adjusted_bcd[digit*4+:4]=bcd[digit*4+:4]+4'd3;
        ascii_value={negative ? 8'h2d:8'h20,8'd48+{4'd0,bcd[19:16]},8'd48+{4'd0,bcd[15:12]},
            8'd48+{4'd0,bcd[11:8]},8'd48+{4'd0,bcd[7:4]},8'd48+{4'd0,bcd[3:0]}};
    end

    // One shared double-dabble converter prepares a coherent text frame off-screen.
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            pending<=0;working<=0;pending_valid<=0;state<=IDLE;field<=0;fusion_pending<=0;fusion_working<=0;
            bit_count<=0;binary<=0;bcd<=0;negative<=0;field_sample<=0;
            for(n=0;n<6;n=n+1) begin lines[n]<={64{8'h20}};work_lines[n]<={64{8'h20}};end
        end else begin
            if(status_update) begin pending<=status_snapshot;pending_valid<=1;fusion_pending<=fusion_snapshot;end
            case(state)
                IDLE:if(pending_valid) begin
                    working<=pending;fusion_working<=fusion_pending;state<=BUILD;
                    if(!status_update) pending_valid<=0;
                end
                BUILD:begin
                    for(n=0;n<6;n=n+1) work_lines[n]<={64{8'h20}};
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
                        working[194] ? "ENC   ":working[196] ? "IMU   ":working[197] ? "TOF   ":working[202] ? "LIDAR ":working[201] ? "TURN  ":"NONE  ";
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
                    work_lines[3][511-:64]<=FUSION_ENABLED!=0 ? "CLEAR F:":"LIDAR F:";work_lines[3][399-:24]<=" L:";
                    work_lines[3][327-:24]<=" R:";work_lines[3][247-:16]<="MM";
                    work_lines[3][223-:40]<=" CFG:";field<=0;state<=LOAD;
                    work_lines[4][511-:56]<="POSE X:";work_lines[4][399-:24]<=" Y:";work_lines[4][319-:16]<="MM";
                    work_lines[4][303-:24]<="PT:";work_lines[4][231-:8]<="/";
                    work_lines[4][167-:32]<="CPU:";
                    work_lines[4][135-:48]<=fusion_working[202] ? "FAULT ":fusion_working[201] ? "OK    ":"WAIT  ";
                    work_lines[5][511-:32]<="NAV:";work_lines[5][423-:56]<="REASON:";work_lines[5][311-:48]<="MATCH:";
                    work_lines[5][207-:40]<="GEOM:";work_lines[5][167-:48]<=fusion_working[24] ? "READY ":"LOCKED";
                    work_lines[5][119-:32]<="NET:";work_lines[5][87-:32]<=working[172] ? "UP  ":"DOWN";
                    if(PANEL_LAYOUT!=0) begin
                        // Two independent 32-character rows per logical line.
                        // Keep each label and signed value together on the 480px panel.
                        for(n=0;n<6;n=n+1) work_lines[n]<={64{8'h20}};
                        work_lines[0][511-0*8-:40]<="MODE:";
                        case(working[183:176])
                            0:work_lines[0][511-5*8-:48]<="DISARM";
                            1:work_lines[0][511-5*8-:48]<="ARMED ";
                            2:work_lines[0][511-5*8-:48]<="DRIVE ";
                            3:work_lines[0][511-5*8-:48]<="FAULT ";
                            4:work_lines[0][511-5*8-:48]<="ROTATE";
                            default:work_lines[0][511-5*8-:48]<="INVAL ";
                        endcase
                        work_lines[0][511-12*8-:40]<="STOP:";
                        work_lines[0][511-17*8-:48]<=working[192] ? "TTL   ":working[194] ? "ENC   ":
                            working[196] ? "IMU   ":working[197] ? "TOF   ":working[202] ? "LIDAR ":working[201] ? "TURN  ":"NONE  ";
                        work_lines[0][511-32*8-:32]<="DDR:";work_lines[0][511-36*8-:40]<=working[168] ? "READY":"WAIT ";
                        work_lines[0][511-42*8-:32]<="CAM:";work_lines[0][511-46*8-:40]<=working[169] ? "READY":"INVAL";
                        work_lines[0][511-52*8-:32]<="FLT:";
                        work_lines[1][511-0*8-:24]<="LT:";work_lines[1][511-10*8-:24]<="LM:";work_lines[1][511-20*8-:32]<="MM/S";
                        work_lines[1][511-32*8-:24]<="RT:";work_lines[1][511-42*8-:24]<="RM:";work_lines[1][511-52*8-:32]<="MM/S";
                        work_lines[2][511-0*8-:32]<="YAW:";work_lines[2][511-10*8-:32]<=" DEG";
                        work_lines[2][511-32*8-:32]<="TOF:";work_lines[2][511-43*8-:40]<="GYRO:";work_lines[2][511-55*8-:40]<="DEG/S";
                        work_lines[3][511-0*8-:64]<="CLEAR F:";work_lines[3][511-15*8-:16]<="MM";
                        work_lines[3][511-32*8-:16]<="L:";work_lines[3][511-41*8-:16]<="R:";work_lines[3][511-50*8-:32]<="CFG:";
                        work_lines[4][511-0*8-:56]<="POSE X:";work_lines[4][511-14*8-:16]<="Y:";work_lines[4][511-23*8-:16]<="MM";
                        work_lines[4][511-32*8-:24]<="PT:";work_lines[4][511-41*8-:8]<="/";work_lines[4][511-49*8-:32]<="CPU:";
                        work_lines[4][511-53*8-:48]<=fusion_working[202] ? "FAULT ":fusion_working[201] ? "OK    ":"WAIT  ";
                        work_lines[5][511-0*8-:32]<="NAV:";work_lines[5][511-11*8-:56]<="REASON:";
                        work_lines[5][511-32*8-:16]<="Q:";work_lines[5][511-41*8-:32]<="GEO:";
                        work_lines[5][511-45*8-:48]<=fusion_working[24] ? "READY ":"LOCKED";
                        work_lines[5][511-52*8-:32]<="NET:";work_lines[5][511-56*8-:32]<=working[172] ? "UP  ":"DOWN";
                    end
                end
                LOAD:begin field_sample<=field_value;state<=SAMPLE;end
                SAMPLE:begin
                    binary<=magnitude>99999 ? 17'd99999:magnitude[16:0];
                    negative<=field_sample[31];bcd<=0;bit_count<=0;state<=CONVERT;
                end
                CONVERT:begin
                    bcd<={adjusted_bcd[18:0],binary[16]};binary<={binary[15:0],1'b0};
                    if(bit_count==16) state<=STORE;else bit_count<=bit_count+1'b1;
                end
                STORE:begin
                    if(PANEL_LAYOUT==0) case(field)
                        0:work_lines[0][143-:48]<=ascii_value;
                        1:work_lines[1][479-:48]<=ascii_value;
                        2:work_lines[1][399-:48]<=ascii_value;
                        3:work_lines[1][311-:48]<=ascii_value;
                        4:work_lines[1][231-:48]<=ascii_value;
                        5:work_lines[2][471-:48]<=working[160] ? ascii_value:"STALE ";
                        6:work_lines[2][343-:48]<=working[162] ? ascii_value:"STALE ";
                        7:work_lines[2][223-:48]<=working[161] ? ascii_value:"STALE ";
                        8:work_lines[3][447-:48]<=working[163] && (FUSION_ENABLED!=0 ? fusion_working[127:112]!=65535:working[479:464]!=65535) ? ascii_value:"INVAL ";
                        9:work_lines[3][375-:48]<=working[163] && working[495:480]!=65535 ? ascii_value:"INVAL ";
                        10:work_lines[3][303-:48]<=working[163] && working[511:496]!=65535 ? ascii_value:"INVAL ";
                        11:work_lines[3][183-:48]<=ascii_value;
                        12:work_lines[4][455-:48]<=working[160] && working[164] ? ascii_value:"STALE ";
                        13:work_lines[4][375-:48]<=working[160] && working[164] ? ascii_value:"STALE ";
                        14:work_lines[5][479-:48]<=ascii_value;
                        15:work_lines[5][367-:48]<=ascii_value;
                        16:work_lines[5][263-:48]<=ascii_value;
                        17:work_lines[4][279-:48]<=ascii_value;
                        18:work_lines[4][223-:48]<=ascii_value;
                    endcase
                    if(PANEL_LAYOUT!=0) case(field)
                        0:work_lines[0][511-56*8-:48]<=ascii_value;
                        1:work_lines[1][511-3*8-:48]<=ascii_value;
                        2:work_lines[1][511-13*8-:48]<=ascii_value;
                        3:work_lines[1][511-35*8-:48]<=ascii_value;
                        4:work_lines[1][511-45*8-:48]<=ascii_value;
                        5:work_lines[2][511-4*8-:48]<=working[160] ? ascii_value:"STALE ";
                        6:work_lines[2][511-36*8-:48]<=working[162] ? ascii_value:"STALE ";
                        7:work_lines[2][511-48*8-:48]<=working[161] ? ascii_value:"STALE ";
                        8:work_lines[3][511-8*8-:48]<=working[163] && fusion_working[127:112]!=65535 ? ascii_value:"INVAL ";
                        9:work_lines[3][511-34*8-:48]<=working[163] && working[495:480]!=65535 ? ascii_value:"INVAL ";
                        10:work_lines[3][511-43*8-:48]<=working[163] && working[511:496]!=65535 ? ascii_value:"INVAL ";
                        11:work_lines[3][511-54*8-:48]<=ascii_value;
                        12:work_lines[4][511-7*8-:48]<=working[160] && working[164] ? ascii_value:"STALE ";
                        13:work_lines[4][511-16*8-:48]<=working[160] && working[164] ? ascii_value:"STALE ";
                        14:work_lines[5][511-4*8-:48]<=ascii_value;
                        15:work_lines[5][511-18*8-:48]<=ascii_value;
                        16:work_lines[5][511-34*8-:48]<=ascii_value;
                        17:work_lines[4][511-35*8-:48]<=ascii_value;
                        18:work_lines[4][511-42*8-:48]<=ascii_value;
                    endcase
                    if(field==(FUSION_ENABLED!=0 ? 18:11)) state<=READY;else begin field<=field+1'b1;state<=LOAD;end
                end
                READY:if(frame_blank) begin
                    for(n=0;n<6;n=n+1) lines[n]<=work_lines[n];
                    state<=IDLE;
                end
                default:state<=IDLE;
            endcase
        end
    // The RGB panel holds its coordinates for at least five sys_clk cycles.
    // Register cell decoding before the character/font mux; HDMI keeps its
    // original zero-latency pixel path (PANEL_LAYOUT=0).
    reg [7:0] panel_ch;
    reg [2:0] panel_col_q,panel_gy_q;reg panel_active_q;
    generate if(PANEL_LAYOUT!=0) begin:panel_render_pipeline
        always @(posedge clk or negedge rst_n)
            if(!rst_n) begin panel_cell<=0;panel_row<=0;panel_gy<=0;panel_active<=0;
                panel_ch<=0;panel_col_q<=0;panel_gy_q<=0;panel_active_q<=0;end
            else begin
                panel_cell<=cell_position(x);panel_row<=y[6:4];panel_gy<=y[3:1];
                panel_active<=de && y<(FUSION_ENABLED!=0 ? 96:64) && x<768;
                panel_ch<=panel_active ? lines[panel_row][511-{panel_cell[8:3],3'b000}-:8]:8'd32;
                panel_col_q<=panel_cell[2:0];panel_gy_q<=panel_gy;panel_active_q<=panel_active;
            end
    end endgenerate
    always @* begin
        rgb=de ? (pixel_valid ? pixel:16'h2104):16'd0;
        pixel_cell=cell_position(x);char_index=pixel_cell[8:3];col=pixel_cell[2:0];row=y[6:4];gy=y[3:1];
        if(PANEL_LAYOUT!=0) begin
            pixel_cell=panel_cell;char_index=panel_cell[8:3];col=panel_col_q;row=panel_row;gy=panel_gy_q;
        end
        glyph_index=6'd34-({3'd0,gy}*6'd5)-{3'd0,col};ch=" ";glyph=0;
        if(PANEL_LAYOUT!=0 ? panel_active_q:(de && y<(FUSION_ENABLED!=0 ? 96:64) && x<768)) begin
            rgb=16'h0022;ch=PANEL_LAYOUT!=0 ? panel_ch:lines[row][511-{char_index,3'b000}-:8];glyph=font(ch);
            if(col<5 && gy<7 && glyph[glyph_index]) rgb=16'hffff;
        end
    end
endmodule
`default_nettype wire
