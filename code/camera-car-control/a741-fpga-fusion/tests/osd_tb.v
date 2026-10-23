`timescale 1ns/1ps
module osd_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,update=0,blank=0;reg [895:0] status=0;
    reg de=1;reg [10:0] x=0,y=100;
    reg [895:0] first_status,second_status,third_status;
    integer elapsed,coordinate;
    wire [15:0] rgb;
    a741_osd dut(.clk(clk),.rst_n(rst),.frame_blank(blank),.de(de),.x(x),.y(y),
        .pixel(16'hf800),.pixel_valid(1'b1),.status_snapshot(status),.status_update(update),.rgb(rgb));
    task publish;
        input [895:0] snapshot;
        begin
            @(negedge clk);status=snapshot;update=1;
            @(negedge clk);update=0;
        end
    endtask
    task prepared;
        begin
            elapsed=0;
            while(dut.state!=dut.READY && elapsed<300) begin @(negedge clk);elapsed=elapsed+1;end
            if(elapsed>=300) $fatal(1,"OSD conversion exceeded bounded latency");
        end
    endtask
    task commit_frame;
        begin @(negedge clk);blank=1;@(negedge clk);blank=0;end
    endtask
    initial begin
        first_status=0;first_status[168]=1;first_status[160]=1;first_status[161]=1;
        first_status[163]=1;first_status[431:416]=-16'sd16384;first_status[447:432]=-16'sd16384;
        first_status[255:224]=-32'sd32768;first_status[287:256]=32'd12345;
        first_status[319:288]=32'h80000000;first_status[351:320]=32'd1000000;
        first_status[479:464]=16'd42;first_status[495:480]=16'hffff;first_status[511:496]=16'd60000;
        first_status[159:128]=32'd74102;
        second_status=first_status;second_status[168]=0;second_status[169]=1;
        second_status[431:416]=16'sd32767;second_status[447:432]=16'sh8000;
        second_status[162]=1;second_status[463:448]=16'd1234;second_status[255:224]=32'd456;
        third_status=second_status;third_status[431:416]=-16'sd1;third_status[255:224]=-32'sd99;
        #50;rst=1;publish(first_status);
        // A vertical blank during conversion must not expose partial text.
        commit_frame;
        if(dut.lines[0]!={64{8'h20}}) $fatal(1,"partial OSD published during conversion");
        prepared;
        if(dut.lines[0]!={64{8'h20}}) $fatal(1,"OSD changed before vertical blank");
        publish(second_status);commit_frame;
        if(dut.lines[0][247-:48]!="READY " || dut.lines[0][63-:48]!="INVAL ") $fatal(1,"DDR/camera validity mixed");
        if(dut.lines[2][471-:48]!="-00090") $fatal(1,"decimal heading sign/units");
        if(dut.lines[2][223-:48]!="-01000") $fatal(1,"decimal gyro sign/units");
        if(dut.lines[2][343-:48]!="STALE ") $fatal(1,"invalid ToF visible");
        if(dut.lines[1][479-:48]!="-32768" || dut.lines[1][311-:48]!=" 12345") $fatal(1,"signed target wheel values");
        if(dut.lines[1][399-:48]!="-99999" || dut.lines[1][231-:48]!=" 99999") $fatal(1,"decimal saturation/minimum signed value");
        if(dut.lines[3][447-:48]!=" 00042" || dut.lines[3][375-:48]!="INVAL " || dut.lines[3][303-:48]!=" 60000") $fatal(1,"LIDAR validity/decimal values");
        if(dut.lines[3][183-:48]!=" 74102") $fatal(1,"configuration revision");
        while(dut.state!=dut.CONVERT || dut.field!=3) @(negedge clk);
        publish(third_status);prepared;
        if(dut.lines[2][471-:48]!="-00090") $fatal(1,"new status tore active text frame");
        commit_frame;
        if(dut.lines[0][247-:48]!="WAIT  " || dut.lines[0][63-:48]!="READY ") $fatal(1,"second atomic status not published");
        if(dut.lines[2][471-:48]!=" 00179" || dut.lines[2][223-:48]!="-02000") $fatal(1,"scaled signed extrema");
        if(dut.lines[2][343-:48]!=" 01234" || dut.lines[1][479-:48]!=" 00456") $fatal(1,"conversion mixed pending snapshot");
        prepared;commit_frame;
        if(dut.lines[2][471-:48]!=" 00000" || dut.lines[1][479-:48]!="-00099") $fatal(1,"latest queued snapshot/round toward zero");
        if(rgb!=16'hf800) $fatal(1,"camera passthrough");
        y=0;
        for(coordinate=0;coordinate<768;coordinate=coordinate+1) begin
            x=coordinate;#1;
            if(dut.char_index!=coordinate/12 || dut.col!=(coordinate%12)/2) $fatal(1,"OSD pixel cell mapping at %0d",coordinate);
        end
        x=768;#1;if(rgb!=16'hf800) $fatal(1,"right edge camera passthrough");
        de=0;#1;if(rgb!=0) $fatal(1,"blanking RGB");
        $display("PASS sequential decimal OSD, bounded conversion, atomic frames, signed limits, invalid labels and pixel mapping");$finish;
    end
    initial begin #100000;$fatal(1,"OSD test timed out");end
endmodule
