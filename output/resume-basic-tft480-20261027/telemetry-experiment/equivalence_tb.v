`timescale 1ns/1ps
module equivalence_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,ready=0,lidar_update=0;
    reg [895:0] snapshot=0;reg [255:0] phy_snapshot=0,fusion_snapshot=0;
    reg [375:0] lidar_packet=0;reg [31:0] lidar_time=0,lidar_seq=0;
    wire [7:0] ad,bd;wire av,bv,al,bl;wire [15:0] an,bn;wire [31:0] ax,bx;
    a741_telemetry #(.PHY_DIAGNOSTICS(1),.FUSION_ENABLED(1)) before_dut(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.snapshot(snapshot),.phy_snapshot(phy_snapshot),
        .fusion_snapshot(fusion_snapshot),.lidar_update(lidar_update),.lidar_packet(lidar_packet),
        .lidar_time(lidar_time),.lidar_seq(lidar_seq),.data(ad),.valid(av),.last(al),.length(an),.ready(ready),.dropped(ax));
    a741_telemetry_candidate #(.PHY_DIAGNOSTICS(1),.FUSION_ENABLED(1)) after_dut(
        .clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),.snapshot(snapshot),.phy_snapshot(phy_snapshot),
        .fusion_snapshot(fusion_snapshot),.lidar_update(lidar_update),.lidar_packet(lidar_packet),
        .lidar_time(lidar_time),.lidar_seq(lidar_seq),.data(bd),.valid(bv),.last(bl),.length(bn),.ready(ready),.dropped(bx));
    reg [31:0] rng=32'h864219ab;integer n,k,bytes=0,packets=0,ems=0,eml=0,emf=0,emp=0;
    initial begin
        repeat(3) @(negedge clk);
        for(n=0;n<120000;n=n+1) begin
            @(negedge clk);rst_n=!(n==9000 || n==70000 || n==91001);
            rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            ms_tick=n%8==0;ready=rng[0] || rng[5];lidar_update=n%313==0 || n%313==1;
            for(k=0;k<28;k=k+1) snapshot[k*32+:32]=rng+k;
            phy_snapshot={8{rng}};fusion_snapshot={8{~rng}};lidar_packet={12{rng}};
            lidar_seq=n;lidar_time=n*17;
            @(posedge clk);#1;
            if({av,al,an,ax}!=={bv,bl,bn,bx}) $fatal(1,"control mismatch n=%d",n);
            if(av && ad!==bd) $fatal(1,"payload mismatch n=%d expected=%h got=%h",n,ad,bd);
            if(av && ready) begin
                bytes=bytes+1;
                if(al) begin
                    packets=packets+1;
                    case(an) 112:ems=ems+1;64:eml=eml+1;48:emf=emf+1;32:emp=emp+1;endcase
                end
            end
        end
        if(ems<100 || eml<100 || emf<100 || emp<10) $fatal(1,"packet coverage missing %d/%d/%d/%d",ems,eml,emf,emp);
        $display("PASS 120000-cycle payload-reset equivalence, random data/backpressure, repeated mid-packet reset; bytes=%d packets=%d EMS=%d EML=%d EMF=%d EMP=%d",bytes,packets,ems,eml,emf,emp);$finish;
    end
endmodule
