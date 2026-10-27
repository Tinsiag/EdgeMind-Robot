`timescale 1ns/1ps
// Compare every output pixel against the user's unmodified official controller,
// not another implementation of its porch equations.
module tft480_reference_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,reference_rst_n=0;
    wire tft_clk,tft_de,tft_hsync,tft_vsync,tft_bl;wire [15:0] tft_rgb;
    a741_tft480_panel #(.BACKLIGHT_FRAMES(1)) dut(.clk(clk),.rst_n(rst_n),
        .rgb(16'hf81f),.tft_clk(tft_clk),.tft_de(tft_de),
        .tft_hsync(tft_hsync),.tft_vsync(tft_vsync),.tft_bl(tft_bl),.tft_rgb(tft_rgb));
    wire ref_de,ref_hs,ref_vs;wire [9:0] ref_x,ref_y;
    TFT_CTRL_480_270_16b official(.Clk9M(tft_clk),.Rst_n(reference_rst_n),.data_in(16'hffff),
        .hcount(ref_x),.vcount(ref_y),.TFT_RGB(),.TFT_HS(ref_hs),.TFT_VS(ref_vs),
        .TFT_CLK(),.TFT_DE(ref_de),.TFT_PWM());
    integer samples=0,pixels=0;time previous_rise=0;
    always @(posedge tft_clk) if(reference_rst_n) begin
        if({tft_de,tft_hsync,tft_vsync}!=={ref_de,ref_hs,ref_vs})
            $fatal(1,"Official reference mismatch at sample%0d: actual%b ref%b",samples,
                {tft_de,tft_hsync,tft_vsync},{ref_de,ref_hs,ref_vs});
        if(previous_rise && $time-previous_rise!=200) $fatal(1,"Reference5MHz period mismatch");
        previous_rise=$time;
        if(tft_de) begin
            if(ref_x>=480 || ref_y>=272) $fatal(1,"Active address beyond reference geometry");
            pixels=pixels+1;
        end else if(tft_rgb!==0) $fatal(1,"Nonblack blanking pixel");
        samples=samples+1;
        if(samples==2*525*286) begin
            if(pixels!=2*480*272 || !tft_bl) $fatal(1,"Incomplete reference frames or backlight");
            $display("PASS two complete480x272 frames match unmodified AC620 controller DE/HS/VS at every5MHz sampling edge");$finish;
        end
    end
    initial begin
        #50;rst_n=1;
        // DUT launches its first pixel on the first falling edge. Keep the
        // reference reset through the preceding rising edge to align pixel0.
        @(posedge tft_clk);#1;reference_rst_n=1;
    end
    initial begin #65000000;$fatal(1,"Official reference watchdog");end
endmodule
