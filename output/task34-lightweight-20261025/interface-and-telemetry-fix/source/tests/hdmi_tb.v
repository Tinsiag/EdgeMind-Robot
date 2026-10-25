`timescale 1ns/1ps
module hdmi_tb;
    reg pixel=0,serial=0,rst=0,de=0;
    always #15 pixel=~pixel;
    always #3 serial=~serial;
    GSR GSR(.GSRI(rst));
    wire cp,cn;wire [2:0] dp,dn;
    a741_hdmi dut(.pixel_clk(pixel),.serial_clk(serial),.reset_clk(pixel),.rst_n(rst),.rgb(16'hf800),
        .de(de),.hsync(1'b1),.vsync(1'b1),.tmds_clk_p(cp),.tmds_clk_n(cn),.tmds_data_p(dp),.tmds_data_n(dn));
    integer ones=0,zeros=0,changes=0;reg previous;
    initial begin
        #100;rst=1;#1000;previous=cp;
        repeat(200) begin
            @(serial);#1;
            if({cp,dp} !== ~{cn,dn}) $fatal(1,"TMDS complement or unknown");
            if(cp) ones=ones+1;else zeros=zeros+1;
            if(cp!=previous) changes=changes+1;previous=cp;
        end
        if(ones<80 || zeros<80 || changes<20) $fatal(1,"TMDS clock inactive");
        de=1;#2000;
        if(dp===3'bxxx) $fatal(1,"TMDS RGB missing");
        #2;rst=0;#1;
        if(dut.serial_reset_pipe!==3'b111) $fatal(1,"serializer reset assertion waited for clock");
        #11;rst=1;
        repeat(2) begin @(posedge pixel);#1;
            if(!dut.serial_reset_pipe[2]) $fatal(1,"serializer reset released before three reset clocks");
        end
        @(posedge pixel);#1;
        if(dut.serial_reset_pipe[2]) $fatal(1,"serializer reset did not release");
        #1000;if({cp,dp} !== ~{cn,dn}) $fatal(1,"TMDS failed after reset");
        $display("PASS dedicated 10:1 serializer, TMDS complementary pairs and active clock");$finish;
    end
endmodule
