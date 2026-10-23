`timescale 1ns/1ps
module ld06_embedded_header_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,byte_valid=0,framing_error=0;
    reg [7:0] data=0,bytes[0:46],crc;
    wire [31:0] errors,sequence_id;
    ld06_parser dut(.clk(clk),.rst_n(rst_n),.ms_tick(1'b0),
        .byte_valid(byte_valid),.framing_error(framing_error),.data(data),
        .errors(errors),.sequence_id(sequence_id));
    task send_byte(input [7:0] value);
        begin
            @(negedge clk);data=value;byte_valid=1;
            @(negedge clk);byte_valid=0;
            repeat(60) @(negedge clk);
        end
    endtask
    task send_frame(input integer embedded,input integer missing,input bad);
        integer i,j;
        begin
            for(i=0;i<47;i=i+1) bytes[i]=0;
            bytes[0]=8'h54;bytes[1]=8'h2c;
            // Equal start/end are legal and also permit embedded angle headers.
            bytes[4]=8'h54;bytes[5]=8'h2c;
            bytes[42]=8'h54;bytes[43]=8'h2c;
            if(embedded>=0) begin bytes[embedded]=8'h54;bytes[embedded+1]=8'h2c;end
            crc=0;
            for(i=0;i<46;i=i+1) begin
                crc=crc^bytes[i];
                for(j=0;j<8;j=j+1) crc=crc[7] ? (crc<<1)^8'h4d:crc<<1;
            end
            bytes[46]=bad ? crc^1:crc;
            for(i=0;i<47;i=i+1) if(i!=missing) send_byte(bytes[i]);
        end
    endtask
    integer k,expected;
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        // Reproduce payload headers, including the captured timestamp 0x2c54.
        expected=0;
        for(k=6;k<=44;k=k+1) begin
            if(k!=41 && k!=42 && k!=43) begin
                send_frame(k,-1,0);expected=expected+1;
                if(sequence_id!=expected || errors!=0) $fatal(1,"payload header offset %0d seq=%0d errors=%0d",k,sequence_id,errors);
            end
        end
        send_frame(-1,-1,1);
        if(errors==0) $fatal(1,"bad CRC was hidden");
        send_frame(-1,-1,0);
        if(sequence_id!=expected+1) $fatal(1,"CRC recovery");
        send_frame(-1,20,0);
        send_frame(-1,-1,0);send_frame(-1,-1,0);
        if(sequence_id<expected+2) $fatal(1,"lost byte recovery");
        @(negedge clk);framing_error=1;
        @(negedge clk);framing_error=0;
        expected=sequence_id;
        send_frame(44,-1,0);
        if(sequence_id!=expected+1) $fatal(1,"framing recovery");
        $display("PASS LD06 embedded payload/timestamp header, CRC, missing byte and framing recovery");$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
