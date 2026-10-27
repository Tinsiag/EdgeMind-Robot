`timescale 1ns/1ps
// Exercise real scanner and OSD with no camera/DDR/PHY, then video restoration.
module display800_diagnostic_tb;
    reg clk=0,rst_n=0;always #15.151515 clk=~clk;
    wire frame_blank,active,pixel_request;
    wire [10:0] x,y;
    wire [15:0] overlay_pixel,osd_rgb,panel_rgb,tft_rgb;
    wire overlay_pixel_valid,tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;
    wire [7:0] led;
    reg pixel_valid=0,camera_error=0,phy_error=0;
    a741_display_diagnostic #(.CLOCK_HZ(10000),.FRAMES_PER_COLOR(2),.WIDTH(800)) diag(
        .clk(clk),.rst_n(rst_n),.frame_blank(frame_blank),.x(x),.pixel(16'h1234),.pixel_valid(pixel_valid),
        .osd_rgb(osd_rgb),.overlay_pixel(overlay_pixel),.overlay_pixel_valid(overlay_pixel_valid),
        .panel_rgb(panel_rgb),.locked(1'b1),.ddr_ready(1'b0),.camera_ready(1'b0),.camera_error(camera_error),
        .phy_ready(1'b0),.phy_error(phy_error),.led(led));
    a741_osd #(.WIDTH(800),.HEIGHT(480),.PIPELINED(1)) osd(.clk(clk),.rst_n(rst_n),.frame_blank(frame_blank),.de(active),.x(x),.y(y),
        .pixel(overlay_pixel),.pixel_valid(overlay_pixel_valid),.status_snapshot(896'd0),
        .fusion_snapshot(256'd0),.status_update(1'b1),.rgb(osd_rgb));
    a741_tft800_panel #(.BACKLIGHT_FRAMES(1)) panel(.clk(clk),.rst_n(rst_n),.rgb(panel_rgb),
        .frame_blank(frame_blank),.active(active),.x(x),.y(y),.pixel_request(pixel_request),
        .tft_clk(tft_clk),.tft_de(tft_de),.tft_hsync(tft_hsync),.tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
    integer frames=0,pixels=0,text_white=0,red_bar=0,live_pixels=0,heartbeats=0;
    integer sampled_x,sampled_y,x0,x1,y0,y1,seen[0:4],s;
    reg [15:0] expected;
    always @(posedge led[1]) if(rst_n) heartbeats=heartbeats+1;
    always @(posedge clk) if(rst_n) begin
        x0<=x;x1<=x0;sampled_x<=x1;y0<=y;y1<=y0;sampled_y<=y1;
        if(frame_blank) begin
            if(pixels!=800*480) $fatal(1,"Missing diagnostic pixels %0d",pixels);
            pixels=0;frames=frames+1;
            #1;
            if(led[2]!==((frames%32)>=16)) $fatal(1,"Frame LED stopped/miscounted");
        end
    end
    always @(posedge tft_clk) if(rst_n && tft_de) begin
        pixels=pixels+1;
        if(frames<10) begin
            s=frames/2;
            case(s)
                0:expected=16'hf800;1:expected=16'h07e0;2:expected=16'h001f;
                3:expected=16'hffff;4:expected=0;
            endcase
            if(tft_rgb!==expected) $fatal(1,"Diagnostic field %0d got %h expected %h",s,tft_rgb,expected);
            seen[s]=seen[s]+1;
        end else if(!pixel_valid) begin
            if(sampled_y>=8 && sampled_y<40 && sampled_x>=208 && sampled_x<592 && tft_rgb==16'hffff)
                text_white=text_white+1;
            if(sampled_y==100 && sampled_x>=500 && sampled_x<600) begin
                if(tft_rgb!==16'hf800) $fatal(1,"Missing-camera fallback bar");
                red_bar=red_bar+1;
            end
        end else if(sampled_y==100) begin
            if(tft_rgb!==16'h1234) $fatal(1,"Live video not restored");
            live_pixels=live_pixels+1;
        end
    end
    initial begin
        for(s=0;s<5;s=s+1) seen[s]=0;
        #1;rst_n=1;#4;rst_n=0;#100;rst_n=1;
        wait(frames==11);#100;pixel_valid=1;camera_error=1;phy_error=1;#1;
        if(led[7:3]!==5'b10100 || !led[0]) $fatal(1,"Initialization error LEDs");
        wait(frames==16);#100;
        if(!tft_bl || text_white==0 || red_bar!=100 || live_pixels!=5*800 || heartbeats==0)
            $fatal(1,"Missing independent display evidence text=%d bars=%d live=%d hb=%d",text_white,red_bar,live_pixels,heartbeats);
        for(s=0;s<5;s=s+1) if(seen[s]!=2*800*480) $fatal(1,"Incomplete field %d",s);
        rst_n=0;#1;
        if(tft_bl || led[2:1]!=0 || panel_rgb!==16'hf800) $fatal(1,"Diagnostic restart/reset");
        $display("PASS 800x480/33MHz diagnostic display: five complete colour fields, no-camera OSD/bars, live video restore, system/frame LEDs, init errors and reset");$finish;
    end
    initial begin #520000000;$fatal(1,"Diagnostic display watchdog");end
endmodule
