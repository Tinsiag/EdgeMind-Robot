`timescale 1ns/1ps
module video_udp_packetizer_tb;
    reg clk=0,rst_n=0,empty=1,ready=0;
    reg [17:0] token=0;
    wire read,valid,first,last;
    wire [7:0] data;
    wire [15:0] length;
    integer cycles=0,count=0,packets=0,index,dump,p;
    reg [7:0] bytes[0:1500];
    reg [15:0] expected_length;
    reg stalled=0;
    reg [7:0] held;
    reg held_first,held_last;
    reg [1023:0] dump_path;
    always #4 clk=~clk;
    video_udp_packetizer #(.WIDTH(5),.HEIGHT(2),.CHUNK_PIXELS(3)) dut(
        .clk(clk),.rst_n(rst_n),.token_data(token),.token_empty(empty),.token_read(read),
        .udp_data(data),.udp_valid(valid),.udp_start(first),.udp_last(last),
        .udp_length(length),.udp_ready(ready));
    always @(negedge clk) begin cycles=cycles+1;ready=(cycles%5<3);end
    always @(posedge clk) if(rst_n) begin
        if(stalled && (!valid || data!==held || first!==held_first || last!==held_last))
            $fatal(1,"FAIL unstable stalled UDP byte");
        stalled=valid && !ready;held=data;held_first=first;held_last=last;
        if(valid && ready) begin
            if(first) begin
                if(count!=0) $fatal(1,"FAIL packet start before previous end");
                expected_length=length;
            end else if(count==0) $fatal(1,"FAIL missing packet start");
            if(length!=expected_length) $fatal(1,"FAIL changing UDP length");
            bytes[count]=data;count=count+1;
            if(last) begin
                if(count!=expected_length) $fatal(1,"FAIL packet byte count");
                for(index=0;index<count;index=index+1) $fwrite(dump,"%02x",bytes[index]);
                $fwrite(dump,"\n");count=0;packets=packets+1;
            end
        end
    end
    task push;
        input [17:0] value;
        begin
            @(negedge clk);token=value;empty=0;
            @(posedge clk);while(!read) @(posedge clk);
            @(negedge clk);empty=1;
        end
    endtask
    initial begin
        if(!$value$plusargs("DUMP=%s",dump_path)) dump_path="packetizer.hex";
        dump=$fopen(dump_path,"w");
        repeat(4) @(negedge clk);rst_n=1;
        push({2'b01,16'd0});
        for(p=0;p<10;p=p+1) push({2'b00,16'h1000+p[15:0]});
        push({2'b10,16'd0});
        push({2'b01,16'd0});
        for(p=0;p<3;p=p+1) push({2'b00,16'h2000+p[15:0]});
        push({2'b11,16'd0});
        push({2'b01,16'd0});
        for(p=0;p<3;p=p+1) push({2'b00,16'h3000+p[15:0]});
        push({2'b10,16'd0});
        repeat(200) @(posedge clk);
        if(packets!=9) $fatal(1,"FAIL expected 9 packets, got %0d",packets);
        $fclose(dump);
        $display("PASS video_udp_packetizer: chunks, stalls, good/bad/truncated frame");
        $finish;
    end
    initial begin #100000; $fatal(1,"FAIL timeout");end
endmodule
