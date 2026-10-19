`timescale 1ns/1ps
module uart_integration_tb;
    localparam CLK_HZ=1000000,BIT_CYCLES=8;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,uart_rx=1;wire uart_tx;
    reg left_a=0,left_b=0,right_a=0,right_b=0;
    reg line_update=0;reg [1:0] regions_valid=3;reg [10:0] near_center=400,far_center=400;
    reg [15:0] line_frame_id=1;reg tof_update=0,tof_valid=1,tof_error=0;
    reg [15:0] distance_mm=700;reg [7:0] range_status=9;reg video_ready=1,video_error=0;
    reg [1:0] video_warning=0;
    wire left_in1,left_in2,right_in1,right_in2;wire [7:0] threshold,led;
    wire [10:0] near_y0,near_y1,far_y0,far_y1;wire [191:0] osd_status;wire ms_tick;
    vision_motion_control #(.CLK_HZ(CLK_HZ)) dut(.*);
    reg [15:0] crc;reg [7:0] seq=0;
    function [15:0] crc_byte;input [15:0] c;input [7:0] d;integer k;reg [15:0] q;
        begin q=c;for(k=0;k<8;k=k+1)q=(q[15]^d[7-k])?((q<<1)^16'h1021):(q<<1);crc_byte=q;end
    endfunction
    task byte_out;input [7:0] d;integer b;begin
        uart_rx=0;repeat(BIT_CYCLES)@(negedge clk);
        for(b=0;b<8;b=b+1)begin uart_rx=d[b];repeat(BIT_CYCLES)@(negedge clk);end
        uart_rx=1;repeat(BIT_CYCLES*2)@(negedge clk);
    end endtask
    task body;input [7:0] d;begin byte_out(d);crc=crc_byte(crc,d);end endtask
    task command;input [7:0] kind,len,version;input [63:0] data;integer b;begin
        seq=seq+1;crc=16'hffff;byte_out(8'haa);byte_out(8'h55);
        body(version);body(kind);body(len);body(seq);body(250);body(0);
        for(b=0;b<len;b=b+1)body(data[b*8+:8]);
        byte_out(crc[7:0]);byte_out(crc[15:8]);repeat(10)@(negedge clk);
    end endtask
    task sensor;begin @(negedge clk);line_update=1;tof_update=1;@(negedge clk);line_update=0;tof_update=0;end endtask
    task start_auto;begin repeat(3)sensor;command(8'h41,1,1,1);command(8'h42,0,1,0);end endtask
    wire [7:0] response_byte;wire response_valid;
    uart_rx #(.CLK_HZ(CLK_HZ)) peer(.clk(clk),.rstn(rst_n),.rx(uart_tx),.data(response_byte),.valid(response_valid),.framing_error());
    reg [7:0] responses[0:1023];integer received=0,i,base;
    integer packet_start=0,crc_index;reg [15:0] response_crc;
    always @(posedge clk)if(response_valid)begin
        responses[received]=response_byte;received=received+1;
        if(received-packet_start>=10 && received-packet_start==responses[packet_start+4]+10)begin
            response_crc=16'hffff;
            for(crc_index=packet_start+2;crc_index<received-2;crc_index=crc_index+1)
                response_crc=crc_byte(response_crc,responses[crc_index]);
            if(response_crc!={responses[received-1],responses[received-2]})$fatal(1,"Reply CRC mismatch");
            if(responses[packet_start]!=8'haa || responses[packet_start+1]!=8'h55 || responses[packet_start+2]!=1)$fatal(1,"Reply envelope mismatch");
            packet_start=received;
        end
    end
    integer plant_ticks=0;reg [1:0] left_phase=0,right_phase=0;
    always @(negedge clk)begin
        plant_ticks=plant_ticks+1;
        if(dut.drive_enable && plant_ticks%1500==0)begin
            // Forward-positive encoder trajectories, not an electromechanical model.
            if(dut.tl>0)begin
                left_phase=left_phase+1'b1;
                case(left_phase)0:{left_a,left_b}=0;1:{left_a,left_b}=1;2:{left_a,left_b}=3;3:{left_a,left_b}=2;endcase
            end
            if(dut.tr>0)begin
                right_phase=right_phase+1'b1;
                case(right_phase)0:{right_a,right_b}=0;1:{right_a,right_b}=2;2:{right_a,right_b}=3;3:{right_a,right_b}=1;endcase
            end
        end
    end
    initial begin
        repeat(5)@(negedge clk);rst_n=1;repeat(10)@(negedge clk);
        command(8'h40,0,1,0);wait(received==18);
        if(responses[3]!=8'hc0 || responses[8]!="E" || responses[11]!="1")$fatal(1,"Capability UART reply invalid");
        command(8'h41,1,2,1);if(dut.auto_mode)$fatal(1,"Wrong version changed mode");
        command(8'h41,0,1,0);if(dut.auto_mode)$fatal(1,"Short mode payload accepted");
        start_auto;if(!dut.armed)$fatal(1,"UART start did not arm reason=%d",dut.reason);
        repeat(15000)@(negedge clk);
        if(!right_in1 && !right_in2 && dut.rp==0)$fatal(1,"No right PI output");
        if(right_in1)$fatal(1,"Right bridge polarity not corrected");
        // Invalid packets must not change mode/targets or keep a manual TTL alive.
        command(8'h44,5,1,64'h000000ff00);if(threshold!=80)$fatal(1,"Running config accepted");
        command(8'h04,0,1,0);if(left_in1 || left_in2 || right_in1 || right_in2 || dut.armed)$fatal(1,"UART STOP failed");
        command(8'h43,0,1,0);repeat(5000)@(negedge clk);
        distance_mm=240;sensor;command(8'h42,0,1,0);if(dut.armed)$fatal(1,"Start over obstacle accepted");
        distance_mm=700;repeat(3)sensor;command(8'h42,0,1,0);if(!dut.armed)$fatal(1,"Manual restart failed");
        // Without PC traffic, fresh sensors keep AUTO alive beyond 250 ms.
        for(i=0;i<31;i=i+1)begin repeat(10000)@(negedge clk);sensor;end
        if(!dut.drive_enable || dut.reason!=0)$fatal(1,"Autonomous run failed without PC, reason=%d faults=%d",dut.reason,dut.motor_faults);
        $display("PASS: actual UART capabilities/version/length/config/STOP, bridge path and explicit restart");$finish;
    end
    initial begin #10000000;$fatal(1,"Watchdog received=%d",received);end
endmodule
