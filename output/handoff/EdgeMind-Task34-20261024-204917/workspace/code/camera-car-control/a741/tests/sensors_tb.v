`timescale 1ns/1ps
module sensors_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,ms=0,iv=0,lv=0;reg [7:0] ib=0,lb=0;
    wire av,gv,pv,lvalid,point_valid;wire [15:0] angle,distance_mm;wire signed [15:0] yaw,gz;
    wire [31:0] ie,le,ls;wire [375:0] raw;
    jy901_parser #(.STALE_MS(5)) imu(.clk(clk),.rst_n(rst_n),.ms_tick(ms),.byte_valid(iv),.framing_error(1'b0),.data(ib),
        .angle_valid(av),.gyro_valid(gv),.yaw(yaw),.gz(gz),.errors(ie));
    ld06_parser #(.STALE_MS(5)) lidar(.clk(clk),.rst_n(rst_n),.ms_tick(ms),.byte_valid(lv),.framing_error(1'b0),.data(lb),
        .packet_valid(pv),.valid(lvalid),.errors(le),.sequence_id(ls),.packet(raw),
        .point_valid(point_valid),.angle_cdeg(angle),.distance_mm(distance_mm));
    integer point_count=0,expected_angle;
    always @(negedge clk) if(point_valid) begin
        expected_angle=35996+(104*point_count)/11;
        if(expected_angle>=36000) expected_angle=expected_angle-36000;
        if(angle!==expected_angle || distance_mm!=1000) $fatal(1,"LD06 interpolation %0d got %0d expected %0d",point_count,angle,expected_angle);
        point_count=point_count+1;
    end
    reg [7:0] buf_i[0:10],buf_l[0:46],sum,crc;integer i,j;
    task ibyte(input [7:0] b);begin @(negedge clk);iv=1;ib=b;@(negedge clk);iv=0;end endtask
    task lbyte(input [7:0] b);begin @(negedge clk);lv=1;lb=b;@(negedge clk);lv=0;end endtask
    task iframe(input [7:0] typ,input [15:0] z,input bad);
        begin
            for(i=0;i<11;i=i+1) buf_i[i]=0;
            buf_i[0]=8'h55;buf_i[1]=typ;buf_i[6]=z[7:0];buf_i[7]=z[15:8];sum=0;
            for(i=0;i<10;i=i+1) sum=sum+buf_i[i];
            buf_i[10]=bad ? sum^1:sum;
            for(i=0;i<11;i=i+1) ibyte(buf_i[i]);
        end
    endtask
    task lframe(input bad);begin
        crc=0;
        for(i=0;i<46;i=i+1) begin
            crc=crc^buf_l[i];
            for(j=0;j<8;j=j+1) crc=crc[7] ? (crc<<1)^8'h4d:crc<<1;
        end
        buf_l[46]=bad ? crc^1:crc;
        for(i=0;i<47;i=i+1) lbyte(buf_l[i]);
        repeat(110) @(negedge clk);
    end endtask
    initial begin
        #50;rst_n=1;
        ibyte(8'h01);iframe(8'h53,16'h7f00,1);
        if(av || ie!=1) $fatal(1,"IMU checksum");
        iframe(8'h53,16'h8100,0);iframe(8'h52,16'hfffe,0);
        if(!av || !gv || yaw!=-32512 || gz!=-2) $fatal(1,"IMU signed resync");
        for(i=0;i<47;i=i+1) buf_l[i]=0;
        buf_l[0]=8'h54;buf_l[1]=8'h2c;
        buf_l[4]=8'h9c;buf_l[5]=8'h8c;
        buf_l[42]=8'h64;buf_l[43]=0;
        for(i=0;i<12;i=i+1) begin buf_l[6+i*3]=8'he8;buf_l[7+i*3]=3;buf_l[8+i*3]=100;end
        lframe(1);if(lvalid || le!=1) $fatal(1,"LD06 CRC");
        lframe(0);if(!lvalid || ls!=1 || raw[15:0]!=16'h2c54) $fatal(1,"LD06 wrap packet");
        if(point_count!=12) $fatal(1,"LD06 point count %0d",point_count);
        repeat(5) begin @(negedge clk);ms=1;@(negedge clk);ms=0;end
        if(av || gv || lvalid) $fatal(1,"sensor stale");
        $display("PASS sensor checksum, CRC, resync, signed data, wrap packet, stale");$finish;
    end
    initial begin #200000;$fatal(1,"watchdog");end
endmodule
