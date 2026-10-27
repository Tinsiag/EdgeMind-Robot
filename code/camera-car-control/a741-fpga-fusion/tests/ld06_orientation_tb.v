`timescale 1ns/1ps
module ld06_orientation_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,byte_valid=0,framing_error=0,ms_tick=0;
    reg [7:0] data=0;wire [15:0] f0,l0,r0,fc,lc,rc,fa,la,ra;
    wire p0,pc,pa;wire [15:0] a0,ac,aa;wire [375:0] raw0,rawc,rawa;
    ld06_parser original(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.byte_valid(byte_valid),.framing_error(framing_error),.data(data),
        .front_mm(f0),.left_mm(l0),.right_mm(r0),.point_valid(p0),.angle_cdeg(a0),.packet(raw0));
    ld06_parser #(.LIDAR_ZERO(27000),.LIDAR_CLOCKWISE(1)) clockwise(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.byte_valid(byte_valid),.framing_error(framing_error),.data(data),
        .front_mm(fc),.left_mm(lc),.right_mm(rc),.point_valid(pc),.angle_cdeg(ac),.packet(rawc));
    ld06_parser #(.LIDAR_ZERO(27000),.LIDAR_CLOCKWISE(0)) anticlockwise(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.byte_valid(byte_valid),.framing_error(framing_error),.data(data),
        .front_mm(fa),.left_mm(la),.right_mm(ra),.point_valid(pa),.angle_cdeg(aa),.packet(rawa));
    integer points=0;
    always @(negedge clk) if(rst_n) begin
        if({p0,a0,raw0}!=={pc,ac,rawc} || {p0,a0,raw0}!=={pa,aa,rawa})
            $fatal(1,"mount transform altered raw telemetry angles or packets");
        if(p0) points=points+1;
    end
    task put(input [7:0] b);begin @(negedge clk);data=b;byte_valid=1;@(negedge clk);byte_valid=0;end endtask
    integer front_distance=1200;
    task frame(input integer first);
        reg [7:0] bytes[0:46],crc;integer i,j,angle,distance,last;
        begin
            for(i=0;i<47;i=i+1) bytes[i]=0;
            bytes[0]=8'h54;bytes[1]=8'h2c;bytes[4]=first;bytes[5]=first>>8;
            last=(first+1100)%36000;bytes[42]=last;bytes[43]=last>>8;
            for(i=0;i<12;i=i+1) begin
                angle=(first+i*100)%36000;
                // Independent physical fixture: front at raw270deg, left180deg,
                // right0deg; no reuse of the RTL's transform expression.
                if(angle>=24000 && angle<=30000) distance=front_distance;
                else if(angle>=15000 && angle<=21000) distance=800;
                else if(angle<=3000 || angle>=33000) distance=900;
                else distance=2000;
                bytes[6+i*3]=distance;bytes[7+i*3]=distance>>8;bytes[8+i*3]=100;
            end
            crc=0;for(i=0;i<46;i=i+1) begin
                crc=crc^bytes[i];for(j=0;j<8;j=j+1) crc=crc[7] ? (crc<<1)^8'h4d:crc<<1;
            end
            bytes[46]=crc;for(i=0;i<47;i=i+1) put(bytes[i]);repeat(110) @(negedge clk);
        end
    endtask
    integer i;
    initial begin
        #50;rst_n=1;
        for(i=0;i<91;i=i+1) frame((i*1200)%36000);
        if(fc!=1200 || lc!=800 || rc!=900 || fa!=1200 || la!=900 || ra!=800)
            $fatal(1,"mount sectors CW=%d/%d/%d CCW=%d/%d/%d",fc,lc,rc,fa,la,ra);
        // Raw zero belongs to a side sector; it must not seed the front minimum.
        if(fc==900 || fa==900) $fatal(1,"raw wrap contaminated front sector");
        if(f0!=900 || l0!=2000 || r0!=1200) $fatal(1,"default raw sector compatibility");
        front_distance=300;
        for(i=91;i<181;i=i+1) frame((i*1200)%36000);
        if(fc!=300 || fa!=300 || lc!=800 || rc!=900) $fatal(1,"front obstacle mapped to wrong side");
        @(negedge clk);framing_error=1;@(negedge clk);framing_error=0;
        if(fc!=65535 || lc!=65535 || rc!=65535) $fatal(1,"framing error retained sectors");
        if(points<2000) $fatal(1,"insufficient real packet interpolation coverage");
        $display("PASS LD06270deg mounting CW/CCW front/left/right, raw-wrap minima, front obstacle and unchanged raw point/packet telemetry");$finish;
    end
    initial begin #5000000;$fatal(1,"orientation watchdog");end
endmodule
