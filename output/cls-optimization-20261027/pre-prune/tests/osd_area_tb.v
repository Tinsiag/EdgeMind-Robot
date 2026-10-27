`timescale 1ns/1ps
module osd_area_case #(parameter FUSION=0,PANEL=0)(
    input wire clk,rst_n,update,blank,de,input wire [10:0] x,y,
    input wire [895:0] status,input wire [255:0] fusion,
    input wire [15:0] pixel,input wire pixel_valid
);
    wire [15:0] actual,expected;
    integer row;
    a741_osd #(.FUSION_ENABLED(FUSION),.PANEL_LAYOUT(PANEL)) dut(
        .clk(clk),.rst_n(rst_n),.frame_blank(blank),.de(de),.x(x),.y(y),
        .pixel(pixel),.pixel_valid(pixel_valid),.status_snapshot(status),
        .status_update(update),.fusion_snapshot(fusion),.rgb(actual));
    a741_osd_area_reference #(.FUSION_ENABLED(FUSION),.PANEL_LAYOUT(PANEL)) reference(
        .clk(clk),.rst_n(rst_n),.frame_blank(blank),.de(de),.x(x),.y(y),
        .pixel(pixel),.pixel_valid(pixel_valid),.status_snapshot(status),
        .status_update(update),.fusion_snapshot(fusion),.rgb(expected));
    always @(posedge clk) begin
        #1;
        if(actual!==expected) $fatal(1,"OSD RGB differs fusion=%0d panel=%0d xy=%0d,%0d",FUSION,PANEL,x,y);
        for(row=0;row<6;row=row+1)
            if(dut.lines[row]!==reference.lines[row])
                $fatal(1,"Published OSD text differs fusion=%0d panel=%0d row=%0d",FUSION,PANEL,row);
    end
endmodule

module osd_area_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,update=0,blank=0,de=0,pixel_valid=0;
    reg [10:0] x=0,y=0;
    reg [895:0] status=0;reg [255:0] fusion=0;reg [15:0] pixel=0;
    integer cycle,i,seed=7412026;
    genvar f,p;
    generate for(f=0;f<2;f=f+1) begin:fm
        for(p=0;p<2;p=p+1) begin:pm
            osd_area_case #(.FUSION(f),.PANEL(p)) check(
                .clk(clk),.rst_n(rst_n),.update(update),.blank(blank),.de(de),
                .x(x),.y(y),.status(status),.fusion(fusion),.pixel(pixel),.pixel_valid(pixel_valid));
        end
    end endgenerate
    initial begin
        repeat(3) @(negedge clk);
        // Queued updates, blanking during conversion, stale/invalid labels,
        // signed extrema, and resets in different conversion/commit stages.
        for(cycle=0;cycle<90000;cycle=cycle+1) begin
            @(negedge clk);
            rst_n=!(cycle<2 || cycle==115 || cycle==18900 || cycle==45800 || cycle==70512);
            blank=(cycle%733)<3;
            update=(cycle%347)==0 || (cycle%347)==1;
            de=(cycle%71)!=0;pixel_valid=(cycle%7)!=0;
            x=cycle%800;y=(cycle/800)%112;pixel=$random(seed);
            if(update) begin
                for(i=0;i<28;i=i+1) status[i*32+:32]=$random(seed);
                for(i=0;i<8;i=i+1) fusion[i*32+:32]=$random(seed);
                status[183:176]=(cycle/347)%7;
                if((cycle/347)%5==0) status[319:288]=32'h80000000;
                if((cycle/347)%5==1) status[479:464]=16'hffff;
            end
        end
        $display("PASS OSD area equivalence: four layouts, 90000 cycles, atomic text/RGB, queued status, reset during conversion");
        $finish;
    end
    initial begin #2000000;$fatal(1,"OSD area test timed out");end
endmodule
