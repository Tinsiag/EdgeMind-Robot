`timescale 1ns/1ps
// Check the LCD interface at its sampling edge, independently of internal counters.
module tft480_timing_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;
    wire [15:0] tft_rgb;
    // Also cover delays beyond the old four-bit startup counter's range.
    a741_tft480_panel #(.BACKLIGHT_FRAMES(17)) dut(
        .clk(clk),.rst_n(rst_n),.snapshot(896'd0),.fusion_snapshot(256'd0),
        .tft_clk(tft_clk),.tft_de(tft_de),.tft_hsync(tft_hsync),
        .tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
    wire default_bl;
    a741_tft480_panel default_delay(.clk(clk),.rst_n(rst_n),
        .snapshot(896'd0),.fusion_snapshot(256'd0),.tft_clk(),.tft_de(),
        .tft_hsync(),.tft_vsync(),.tft_bl(default_bl),.tft_rgb());
    integer h=0,v=0,frames=0;
    reg started=0;
    time last_rising=0,last_falling=0,last_change=0,frame_start=0;
    reg previous_vs=1;
    always @(negedge rst_n) begin
        h=0;v=0;frames=0;started=0;previous_vs=1;
        last_rising=0;last_falling=0;last_change=0;frame_start=0;
    end
    always @(tft_rgb or tft_de or tft_hsync or tft_vsync) if(rst_n) begin
        if(tft_clk!==0) $fatal(1,"LCD data changed while PCLK high");
        if(last_rising!=0 && $time-last_rising<40) $fatal(1,"LCD hold below 40ns");
        last_change=$time;
    end
    always @(negedge tft_clk) if(rst_n) begin
        if(last_rising!=0 && $time-last_rising!=40) $fatal(1,"PCLK high pulse must be 40ns");
        last_falling=$time;
    end
    always @(posedge tft_clk) if(rst_n) begin
        if(last_rising!=0 && $time-last_rising!=100) $fatal(1,"PCLK must have a fixed 100ns period");
        if(last_falling!=0 && $time-last_falling!=60) $fatal(1,"PCLK low pulse must be 60ns");
        if(last_change!=0 && $time-last_change<60) $fatal(1,"LCD setup below 60ns");
        last_rising=$time;
        if(previous_vs && !tft_vsync) begin
            if(started) begin
                if($time-frame_start!=15015000) $fatal(1,"frame period changed");
                frames=frames+1;
            end else begin started=1;h=0;v=0;end
            frame_start=$time;
        end
        previous_vs=tft_vsync;
        if(started) begin
            // AT043TN24: 41+2+480+2 clocks, 10+2+272+2 lines.
            if(tft_hsync!==(h>=41) || tft_vsync!==(v>=10))
                $fatal(1,"sync boundary at %0d,%0d",h,v);
            if(tft_de!==((h>=43 && h<523) && (v>=12 && v<284)))
                $fatal(1,"DE boundary at %0d,%0d",h,v);
            if(!tft_de && tft_rgb!==0) $fatal(1,"RGB must be black in blanking");
            if(tft_bl!==(frames>=17)) $fatal(1,"backlight delay at frame %0d",frames);
            if(default_bl!==(frames>=11)) $fatal(1,"default LED startup must wait at least 160ms");
            if(h==524) begin h=0;if(v==285) v=0;else v=v+1;end
            else h=h+1;
        end
    end
    task reset_panel;
        begin
            rst_n=0;#1;
            if({tft_clk,tft_de,tft_bl,tft_rgb}!==19'd0 || {tft_hsync,tft_vsync}!==2'b11)
                $fatal(1,"reset did not blank LCD and backlight");
            #46;rst_n=1;
        end
    endtask
    initial begin
        // Assert reset explicitly, then repeat during active pixels at a different phase.
        #1;rst_n=1;#7;reset_panel();
        wait(frames==1);wait(tft_de);#13;reset_panel();
        wait(frames==17);#1;
        if(!tft_bl) $fatal(1,"long startup delay never enabled backlight");
        $display("PASS fixed 10MHz PCLK, full 525x286/480x272 boundaries, setup/hold, blanking, active-frame reset, 165ms default and 17-frame backlight");
        $finish;
    end
    initial begin #300000000;$fatal(1,"LCD timing watchdog");end
endmodule
