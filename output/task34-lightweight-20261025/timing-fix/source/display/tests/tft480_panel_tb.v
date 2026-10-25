`timescale 1ns/1ps
module tft480_panel_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0;reg [895:0] snapshot=0;reg [255:0] fusion_snapshot=0;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;wire [15:0] tft_rgb;
    a741_tft480_panel #(.BACKLIGHT_FRAMES(2)) dut(.*);
    time last_edge=0,last_rising=0,last_data_change=0;
    integer frames=0,lines=0,pixels=0,line_pixels=0,line_active=0,line_sync=0;
    integer frame_file=0;reg [2047:0] frame_path;
    reg old_hs=1,old_vs=1,have_line=0;
    reg [8:0] reference_cell;reg [7:0] reference_ch;reg [34:0] reference_glyph;
    reg [15:0] reference_rgb;
    // The panel consumes its OSD output only on falling PCLK enables. Compare
    // every consumed text pixel against a zero-latency character/font lookup.
    always @(posedge clk) if(rst_n && dut.falling && dut.content) begin
        reference_cell=dut.osd.cell_position(dut.osd_x);
        reference_ch=dut.osd.lines[dut.osd_y[6:4]][511-{reference_cell[8:3],3'b000}-:8];
        reference_glyph=dut.osd.font(reference_ch);reference_rgb=16'h0022;
        if(reference_cell[2:0]<5 && dut.osd_y[3:1]<7 &&
           reference_glyph[34-dut.osd_y[3:1]*5-reference_cell[2:0]]) reference_rgb=16'hffff;
        if(dut.osd_rgb!==reference_rgb) $fatal(1,"pipelined panel pixel changed at %0d,%0d",dut.x,dut.y);
    end
    // Compare the narrowed decoder with the original expressions at every
    // title pixel, including the x=256 wrap in the eight-bit offset.
    always @(negedge clk) if(rst_n && dut.title_area) begin
        if(dut.title_index!==8'((dut.x-144)/12) ||
           dut.title_col!==3'(((dut.x-144)%12)/2) || dut.title_row!==3'((dut.y-24)/2))
            $fatal(1,"title pixel changed at %0d,%0d",dut.x,dut.y);
    end
    always @(tft_clk) if(rst_n) begin
        if(last_edge && $time-last_edge<40) $fatal(1,"PCLK pulse below 40ns");
        last_edge=$time;
    end
    always @(tft_rgb or tft_de or tft_hsync or tft_vsync) if(rst_n) last_data_change=$time;
    always @(posedge tft_clk) if(rst_n) begin
        if(last_rising && ($time-last_rising<100 || $time-last_rising>120)) $fatal(1,"PCLK period outside 100/120ns");
        last_rising=$time;
        if($time-last_data_change<40) $fatal(1,"LCD data setup below 40ns");
        if(old_vs && !tft_vsync) begin
            if(frames>0) begin
                if(pixels!=480*272 || lines!=286) $fatal(1,"frame geometry pixels=%0d lines=%0d",pixels,lines);
                if(frames==1 && tft_bl) $fatal(1,"backlight enabled before two complete frames");
                if(frames==2) begin
                    if(!tft_bl) $fatal(1,"backlight did not enable");
                    if(dut.title[127-:64]!="EDGEMIND" || dut.font("K")==0 || dut.osd.font("K")==0 ||
                       dut.osd.font("Q")==0 || dut.osd.font("X")==0) $fatal(1,"title/status glyph missing");
                    if(dut.osd.lines[1][511-13*8-:48]!="-00100") $fatal(1,"signed left wheel not displayed");
                    if(dut.osd.lines[3][511-8*8-:48]!=" 00345") $fatal(1,"body clearance not displayed");
                    if(dut.osd.lines[4][511-35*8-:48]!=" 00003" || dut.osd.lines[4][511-42*8-:48]!=" 00005") $fatal(1,"waypoint progress not displayed");
                    $display("PASS AT043TN24 480x272/525x286, 9MHz PCLK bounds, setup margins, startup backlight and signed status text");$finish;
                end
            end
            frames=frames+1;pixels=0;lines=0;
        end
        if(old_hs && !tft_hsync) begin
            if(have_line && (line_pixels!=525 || line_sync!=41 || (line_active!=0 && line_active!=480)))
                $fatal(1,"line geometry pixels=%0d sync=%0d active=%0d",line_pixels,line_sync,line_active);
            have_line=1;line_pixels=0;line_active=0;line_sync=0;lines=lines+1;
        end
        if(have_line) begin line_pixels=line_pixels+1;if(!tft_hsync) line_sync=line_sync+1;end
        if(tft_de) begin
            pixels=pixels+1;line_active=line_active+1;
            if(frame_file && frames==2) $fwrite(frame_file,"%0d %0d %0d\n",
                (tft_rgb[15:11]*255)/31,(tft_rgb[10:5]*255)/63,(tft_rgb[4:0]*255)/31);
        end
        old_hs=tft_hsync;old_vs=tft_vsync;
    end
    initial begin
        if($value$plusargs("FRAME=%s",frame_path)) begin
            frame_file=$fopen(frame_path,"w");$fwrite(frame_file,"P3\n480 272\n255\n");
        end
        snapshot[319:288]=-100;snapshot[351:320]=125;snapshot[431:416]=16384;
        snapshot[169:168]=3;snapshot[172]=1;snapshot[163]=1;snapshot[160]=1;snapshot[164]=1;
        snapshot[159:128]=74106;fusion_snapshot[127:112]=345;
        fusion_snapshot[199:168]=32'h00040502;fusion_snapshot[202:200]=3'b011;
        snapshot[255:224]=150;snapshot[287:256]=150;snapshot[183:176]=2;
        snapshot[511:496]=1280;snapshot[495:480]=960;
        fusion_snapshot[15:8]=4;fusion_snapshot[24]=1;fusion_snapshot[167:160]=95;
        fusion_snapshot[63:32]=1250;fusion_snapshot[95:64]=-500;
        #50;rst_n=1;
    end
    initial begin #40000000;$fatal(1,"TFT watchdog");end
endmodule
