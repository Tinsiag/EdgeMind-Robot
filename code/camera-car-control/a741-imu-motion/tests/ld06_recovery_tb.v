`timescale 1ns/1ps
module ld06_recovery_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,ms_tick=0,byte_valid=0;
    reg [7:0] data=0;
    wire valid,packet_valid;
    wire [31:0] errors,sequence_id;
    wire [15:0] front_mm,left_mm,right_mm;
    ld06_parser #(.STALE_MS(5)) dut(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),
        .byte_valid(byte_valid),.framing_error(1'b0),.data(data),.valid(valid),
        .packet_valid(packet_valid),.errors(errors),.sequence_id(sequence_id),
        .front_mm(front_mm),.left_mm(left_mm),.right_mm(right_mm));

    task send_byte;
        input [7:0] value;
        begin @(negedge clk);data=value;byte_valid=1;@(negedge clk);byte_valid=0;end
    endtask
    task send_frame;
        input integer first_angle;
        input bad_crc;
        reg [7:0] bytes[0:46];
        reg [7:0] crc;
        integer i,j,point_angle,point_distance,end_angle;
        begin
            for(i=0;i<47;i=i+1) bytes[i]=0;
            bytes[0]=8'h54;bytes[1]=8'h2c;
            bytes[4]=first_angle;bytes[5]=first_angle>>8;
            end_angle=(first_angle+1100)%36000;
            bytes[42]=end_angle;bytes[43]=end_angle>>8;
            for(i=0;i<12;i=i+1) begin
                point_angle=(first_angle+i*100)%36000;
                if(point_angle<=3000 || point_angle>=33000) point_distance=1200;
                else if(point_angle>=4500 && point_angle<=13500) point_distance=800;
                else if(point_angle>=22500 && point_angle<=31500) point_distance=900;
                else point_distance=1500;
                bytes[6+i*3]=point_distance;bytes[7+i*3]=point_distance>>8;bytes[8+i*3]=100;
            end
            crc=0;
            for(i=0;i<46;i=i+1) begin
                crc=crc^bytes[i];
                for(j=0;j<8;j=j+1) crc=crc[7] ? (crc<<1)^8'h4d:crc<<1;
            end
            bytes[46]=bad_crc ? crc^1:crc;
            for(i=0;i<47;i=i+1) send_byte(bytes[i]);
            repeat(110) @(negedge clk);
        end
    endtask
    task no_complete_scan;
        begin
            if(front_mm!=65535 || left_mm!=65535 || right_mm!=65535)
                $fatal(1,"partial recovery scan published as current F/L/R=%0d/%0d/%0d",front_mm,left_mm,right_mm);
        end
    endtask
    integer mode,packet_index,j;
    initial begin
        for(mode=0;mode<2;mode=mode+1) begin
            @(negedge clk);rst_n=0;
            repeat(3) @(negedge clk);rst_n=1;
            // Leave a high previous angle, then lose continuity before recovery at 100 degrees.
            send_frame(33900,0);
            if(dut.last_angle!=35000 || !dut.have_last) $fatal(1,"initial angular history");
            if(mode==0) begin
                send_frame(35100,1);
                if(errors!=1 || sequence_id!=1 || dut.have_last) $fatal(1,"bad CRC did not discard angular continuity");
            end else begin
                for(j=0;j<5;j=j+1) begin @(negedge clk);ms_tick=1;@(negedge clk);ms_tick=0;end
                if(valid || dut.have_last) $fatal(1,"stale data retained angular continuity");
            end
            send_frame(10000,0);
            if(!valid || dut.scan_started) $fatal(1,"recovery at 100 degrees masqueraded as zero crossing");
            no_complete_scan;
            // Consecutive one-degree points cross zero once to start, then again to complete a scan.
            for(packet_index=1;packet_index<=51;packet_index=packet_index+1) begin
                send_frame((10000+packet_index*1200)%36000,0);
                if(packet_index<51) no_complete_scan;
            end
            if(front_mm!=1200 || left_mm!=800 || right_mm!=900)
                $fatal(1,"recovered full scan sectors F/L/R=%0d/%0d/%0d",front_mm,left_mm,right_mm);
        end
        $display("PASS LD06 bad-packet/stale recovery rejects false wrap and publishes only a complete continuous scan");
        $finish;
    end
    initial begin #1000000;$fatal(1,"LD06 recovery watchdog");end
endmodule
