`timescale 1ns/1ps
// Compare both half-cycles AFTER sequential/combinational updates against the
// unmodified official controller. The previous posedge/pre-NBA comparison hid
// an inverted launch/sample phase and did not establish waveform equivalence.
module tft480_reference_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,reference_rst_n=0;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;wire [15:0] tft_rgb;
    wire [10:0] x,y;
    a741_tft480_panel #(.BACKLIGHT_FRAMES(1)) dut(.clk(clk),.rst_n(rst_n),
        .rgb({x[7:0],y[7:0]}),.x(x),.y(y),.tft_clk(tft_clk),.tft_de(tft_de),
        .tft_hsync(tft_hsync),.tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
    wire ref_de,ref_hs,ref_vs;wire [9:0] ref_x,ref_y;wire [15:0] ref_rgb;
    TFT_CTRL_480_270_16b official(.Clk9M(tft_clk),.Rst_n(reference_rst_n),.data_in({ref_x[7:0],ref_y[7:0]}),
        .hcount(ref_x),.vcount(ref_y),.TFT_RGB(ref_rgb),.TFT_HS(ref_hs),.TFT_VS(ref_vs),
        .TFT_CLK(),.TFT_DE(ref_de),.TFT_PWM());
    integer samples=0,pixels=0;time previous_fall=0;
    always @(tft_clk) if(reference_rst_n) begin
        #1;
        if({tft_de,tft_hsync,tft_vsync,tft_rgb}!=={ref_de,ref_hs,ref_vs,ref_rgb})
            $fatal(1,"Official waveform mismatch at sample%0d clock%b: actual %b/%h ref %b/%h",samples,tft_clk,
                {tft_de,tft_hsync,tft_vsync},tft_rgb,{ref_de,ref_hs,ref_vs},ref_rgb);
    end
    always @(negedge tft_clk) if(reference_rst_n) begin
        if(previous_fall && $time-previous_fall!=200) $fatal(1,"Reference5MHz period mismatch");
        previous_fall=$time;
        if(tft_de) begin
            if(ref_x>=480 || ref_y>=272) $fatal(1,"Active address beyond reference geometry");
            pixels=pixels+1;
        end else if(tft_rgb!==0) $fatal(1,"Nonblack blanking pixel");
        samples=samples+1;
        if(samples==2*525*286) begin
            if(pixels!=2*480*272 || !tft_bl) $fatal(1,"Incomplete reference frames or backlight");
            #2;
            $display("PASS two complete480x272 frames match unmodified AC620 DE/HS/VS/RGB after BOTH edges; panel samples FALLING PCLK");$finish;
        end
    end
    initial begin
        #50;rst_n=1;
        // DUT launches count0 on its first rising edge. Hold the reference at
        // count0 through that edge, then both advance together on later rises.
        @(posedge tft_clk);#1;reference_rst_n=1;
    end
    initial begin #65000000;$fatal(1,"Official reference watchdog");end
endmodule
