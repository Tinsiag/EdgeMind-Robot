`timescale 1ns/1ps
module hdmi_tb;
    reg serial_clk=0,reset_clk=0,rst_n=1;
    wire pixel_clk,cp,cn;
    wire [2:0] dp,dn;
    wire [3:0] serial_resets,all_set;
    GSR GSR(.GSRI(1'b1));
    always #3 serial_clk=~serial_clk;
    initial begin #3; forever begin reset_clk=1; #9; reset_clk=0; #9; end end
    CLKDIV #(.DIV_MODE("5")) divider(.CLKOUT(pixel_clk),.CALIB(1'b1),
        .HCLKIN(serial_clk),.RESETN(rst_n));
    a741_hdmi dut(.pixel_clk(pixel_clk),.serial_clk(serial_clk),.reset_clk(reset_clk),
        .rst_n(rst_n),.rgb(16'hf800),.de(1'b1),.hsync(1'b1),.vsync(1'b1),
        .tmds_clk_p(cp),.tmds_clk_n(cn),.tmds_data_p(dp),.tmds_data_n(dn));
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1) begin
        assign serial_resets[lane]=dut.lanes[lane].serial_reset_pipe[2];
        assign all_set[lane]=&dut.lanes[lane].serial_reset_pipe;
    end endgenerate
    integer trial,phase,mask=0,ones,zeros,changes;
    reg previous;
    initial begin
        #1;
        for(trial=0;trial<5;trial=trial+1) begin
            rst_n=0; #1;
            if(all_set!==4'b1111) $fatal(1,"local reset did not assert asynchronously");
            #(900-($time%900)); #60; #(trial*6+1);
            rst_n=1;
            repeat(2) begin
                @(posedge reset_clk); #1;
                if(serial_resets!==4'b1111) $fatal(1,"early local reset release");
            end
            @(posedge reset_clk); #1;
            if(serial_resets!==4'b0000) $fatal(1,"local reset failed to release together");
            repeat(5) @(posedge pixel_clk);
            phase=($time-3)%30; mask=mask | (1 << (phase/6));
            #300;
            ones=0; zeros=0; changes=0; previous=cp;
            repeat(200) begin
                @(serial_clk); #1;
                if({cp,dp} !== ~{cn,dn}) $fatal(1,"TMDS complement/unknown at phase %0d",phase);
                if(cp) ones=ones+1; else zeros=zeros+1;
                if(cp!=previous) changes=changes+1;
                previous=cp;
            end
            if(ones<80 || zeros<80 || changes<20) $fatal(1,"inactive TMDS at phase %0d",phase);
            $display("PASS local reset and active TMDS at pixel phase %0d",phase);
        end
        if(mask!=31) $fatal(1,"incomplete startup phase coverage: %0d",mask);
        $display("PASS all five CLKDIV startup phases, repeated reset, four local reset pipelines");
        $finish;
    end
    initial begin #20000; $fatal(1,"HDMI phase test timeout"); end
endmodule
