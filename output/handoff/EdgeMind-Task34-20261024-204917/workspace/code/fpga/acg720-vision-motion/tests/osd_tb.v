`timescale 1ns/1ps
module osd_tb;
    reg clk=0;always #5 clk=~clk;reg rst_n=0,frame_blank=0,de=1;
    reg [10:0] x=100,y=370;reg [15:0] camera_pixel=16'h1234;reg camera_valid=1;
    reg [191:0] status_snapshot=0;reg status_update=0;wire [15:0] rgb;
    video_osd dut(.*);
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        status_snapshot={69'd0,8'd2,16'd100,16'd100,16'd240,1'b1,11'd299,11'd260,11'd399,11'd360,11'd100,11'd100};
        status_update=1;@(negedge clk);status_update=0;
        if(rgb!=16'h1234)$fatal(1,"OSD changed snapshot midframe");
        frame_blank=1;@(negedge clk);frame_blank=0;#1;
        if(rgb!=16'hf800)$fatal(1,"Line marker not drawn");
        x=200;#1;if(rgb!=camera_pixel)$fatal(1,"Camera pixel not preserved");
        camera_valid=0;#1;if(rgb!=16'h780f)$fatal(1,"No diagnostic background");
        $display("PASS: frame-latched OSD, line marker, camera passthrough and diagnostic background");$finish;
    end
endmodule
