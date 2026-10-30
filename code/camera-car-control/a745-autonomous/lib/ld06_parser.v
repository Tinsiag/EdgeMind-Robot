`timescale 1ns/1ps
`default_nettype none
// LD06: 54 2c, speed, start-angle, 12*(distance,confidence), end-angle,
// device timestamp, CRC8(poly 4d). Stream only packets that passed CRC.
module ld06_parser #(parameter STALE_MS=300,LIDAR_ZERO=0,LIDAR_CLOCKWISE=0)(
    input wire clk,rst_n,ms_tick,byte_valid,framing_error,input wire [7:0] data,
    output reg packet_valid,valid,point_valid,
    output reg [15:0] angle_cdeg,distance_mm,
    output reg [7:0] confidence,
    output reg [375:0] packet,
    output reg [31:0] sample_time,sequence_id,errors,dropped,
    output reg [15:0] front_mm,left_mm,right_mm
);
    reg [375:0] window,candidate;
    // Keep the packet capture enable local to eight register banks.  A single
    // 376-bit register made Gowin promote the capture CE to a PRIMARY clock
    // resource because it fanned out to every bit.  The banks are equivalent
    // state: the concatenated wire below preserves the original packet layout
    // for CRC and telemetry logic while limiting CE fanout to eight loads.
    reg [46:0] checked_packet_0,checked_packet_1,checked_packet_2,checked_packet_3;
    reg [46:0] checked_packet_4,checked_packet_5,checked_packet_6,checked_packet_7;
    wire [375:0] checked_packet={checked_packet_7,checked_packet_6,checked_packet_5,checked_packet_4,
                                 checked_packet_3,checked_packet_2,checked_packet_1,checked_packet_0};
    reg [5:0] filled,packet_guard;
    reg [7:0] crc;
    reg checking,interpolation_ready,divide_start;
    reg [5:0] crc_index;
    reg [15:0] point_step,point_remainder,point_offset;
    reg [4:0] residue;
    wire divide_done,divide_busy;
    wire [31:0] divide_result;
    a741_divider interpolation(.clk(clk),.rst_n(rst_n),.cancel(framing_error),.start(divide_start),
        .numerator({16'd0,span}),.denominator(16'd11),.busy(divide_busy),.done(divide_done),.quotient(divide_result));
    reg [15:0] age;
    reg [31:0] now_ms;
    reg emitting;
    reg [3:0] point_index;
    reg [15:0] start_angle,span,offset,candidate_span;
    reg [31:0] angle_sum;
    reg [15:0] p_angle,p_dist;
    reg [7:0] p_conf;
    reg [15:0] scan_front,scan_left,scan_right,last_angle;
    reg scan_started;
    reg have_last;
    reg emitted_first;
    reg [15:0] last_step,gap_angle;
    // Preserve raw angle/packet outputs. Only body-relative avoidance sectors
    // apply the same mounting transform used by the manual protection guard.
    wire [16:0] shifted_angle=LIDAR_CLOCKWISE!=0 ?
        17'(LIDAR_ZERO)+17'd36000-{1'b0,angle_cdeg}:
        {1'b0,angle_cdeg}+17'd36000-17'(LIDAR_ZERO);
    wire [15:0] sector_angle=16'(shifted_angle>=36000 ? shifted_angle-36000:shifted_angle);
    wire in_front=sector_angle<=3000 || sector_angle>=33000;
    wire in_left=sector_angle>=4500 && sector_angle<=13500;
    wire in_right=sector_angle>=22500 && sector_angle<=31500;
    wire usable=confidence>=10 && distance_mm>0;
    integer k;
    function [7:0] crc_byte;
        input [7:0] c,b;reg [7:0] v;integer n;
        begin v=c^b;for(n=0;n<8;n=n+1) v=v[7] ? (v<<1)^8'h4d:v<<1;crc_byte=v;end
    endfunction
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            window<=0;filled<=0;packet_guard<=0;packet_valid<=0;valid<=0;point_valid<=0;packet<=0;
            angle_cdeg<=0;distance_mm<=0;confidence<=0;sample_time<=0;sequence_id<=0;
            errors<=0;dropped<=0;age<=65535;now_ms<=0;emitting<=0;point_index<=0;
            start_angle<=0;span<=0;scan_front<=65535;scan_left<=65535;scan_right<=65535;
            checked_packet_0<=0;checked_packet_1<=0;checked_packet_2<=0;checked_packet_3<=0;
            checked_packet_4<=0;checked_packet_5<=0;checked_packet_6<=0;checked_packet_7<=0;
            checking<=0;crc_index<=0;crc<=0;interpolation_ready<=0;divide_start<=0;
            point_step<=0;point_remainder<=0;point_offset<=0;residue<=0;emitted_first<=0;
            front_mm<=65535;left_mm<=65535;right_mm<=65535;last_angle<=0;scan_started<=0;have_last<=0;last_step<=0;
        end else begin
            packet_valid<=0;point_valid<=0;divide_start<=0;
            if(ms_tick) begin
                now_ms<=now_ms+1'b1;if(age!=65535) age<=age+1'b1;
                if(age>=STALE_MS-1) begin
                    valid<=0;front_mm<=65535;left_mm<=65535;right_mm<=65535;
                    scan_front<=65535;scan_left<=65535;scan_right<=65535;scan_started<=0;have_last<=0;
                end
            end
            if(emitting && !interpolation_ready && divide_done) begin
                point_step<=divide_result[15:0];point_remainder<=span-divide_result[15:0]*16'd11;
                point_offset<=0;residue<=0;interpolation_ready<=1;last_step<=divide_result[15:0];
            end
            if(emitting && interpolation_ready) begin
                offset=point_offset;
                angle_sum=start_angle+offset;
                p_angle=angle_sum>=36000 ? angle_sum-36000:angle_sum;
                k=6+point_index*3;p_dist=packet[k*8+:16];p_conf=packet[(k+2)*8+:8];
                angle_cdeg<=p_angle;distance_mm<=p_dist;confidence<=p_conf;point_valid<=1;
                emitted_first<=point_index==0;
                if(point_index==11) begin emitting<=0;interpolation_ready<=0;end
                else begin
                    point_index<=point_index+1'b1;
                    if(residue+point_remainder>=11) begin
                        point_offset<=point_offset+point_step+1'b1;residue<=residue+point_remainder-11;
                    end else begin point_offset<=point_offset+point_step;residue<=residue+point_remainder;end
                end
            end
            // Sector telemetry consumes the already registered point. The
            // raw point output keeps its original latency; avoid a RAM
            // byte selection + angle/gap calculation + min comparison in one
            // cycle. Invalidating the stream must also discard this stage.
            if(point_valid && valid && !framing_error && !(ms_tick && age>=STALE_MS-1)) begin
                gap_angle=angle_cdeg>=last_angle ? angle_cdeg-last_angle:angle_cdeg+36000-last_angle;
                if(emitted_first && have_last && gap_angle>(last_step*3>100 ? last_step*3:100)) begin
                    front_mm<=65535;left_mm<=65535;right_mm<=65535;scan_started<=0;
                    scan_front<=65535;scan_left<=65535;scan_right<=65535;dropped<=dropped+1'b1;
                end else if(have_last && angle_cdeg+18000<last_angle) begin
                    if(scan_started) begin front_mm<=scan_front;left_mm<=scan_left;right_mm<=scan_right;end
                    // The raw zero crossing can be a side sector after rotation.
                    scan_front<=usable && in_front ? distance_mm:16'hffff;
                    scan_left<=usable && in_left ? distance_mm:16'hffff;
                    scan_right<=usable && in_right ? distance_mm:16'hffff;scan_started<=1;
                end else if(usable) begin
                    if(in_front && distance_mm<scan_front) scan_front<=distance_mm;
                    if(in_left && distance_mm<scan_left) scan_left<=distance_mm;
                    if(in_right && distance_mm<scan_right) scan_right<=distance_mm;
                end
                last_angle<=angle_cdeg;have_last<=1;
            end
            // UART bytes are thousands of clocks apart. Check one CRC byte per
            // clock instead of cascading all 46 bytes into one combinational path.
            if(checking) begin
                if(crc_index<46) begin crc<=crc_byte(crc,checked_packet[crc_index*8+:8]);crc_index<=crc_index+1'b1;end
                else begin
                    checking<=0;
                    candidate_span=checked_packet[351:336]>=checked_packet[47:32] ?
                        checked_packet[351:336]-checked_packet[47:32]:checked_packet[351:336]+36000-checked_packet[47:32];
                    if(crc!=checked_packet[375:368] || checked_packet[47:32]>=36000 || checked_packet[351:336]>=36000 || candidate_span>3600) begin
                        errors<=errors+1'b1;scan_started<=0;have_last<=0;
                        front_mm<=65535;left_mm<=65535;right_mm<=65535;
                    end else if(emitting) dropped<=dropped+1'b1;
                    else begin
                        packet<=checked_packet;packet_valid<=1;valid<=1;age<=0;sample_time<=now_ms;
                        sequence_id<=sequence_id+1'b1;emitting<=1;point_index<=0;interpolation_ready<=0;divide_start<=1;
                        start_angle<=checked_packet[47:32];span<=candidate_span;
                        packet_guard<=46;
                    end
                end
            end
            if(framing_error) begin filled<=0;packet_guard<=0;errors<=errors+1'b1;scan_started<=0;have_last<=0;
                checking<=0;emitting<=0;interpolation_ready<=0;valid<=0;point_valid<=0;
                front_mm<=65535;left_mm<=65535;right_mm<=65535;
            end
            else if(byte_valid) begin
                candidate={data,window[375:8]};window<=candidate;
                if(filled<47) filled<=filled+1'b1;
                // A validated packet's payload cannot start another packet.
                if(packet_guard!=0) packet_guard<=packet_guard-1'b1;
                else if(filled>=46 && candidate[15:0]==16'h2c54) begin
                    if(checking) dropped<=dropped+1'b1;
                    else begin
                        // Use an explicit D-side hold mux instead of one
                        // shared CE across all 376 capture flops.  Gowin then
                        // keeps this packet token on ordinary data routing;
                        // the packet layout and byte ordering are unchanged.
                        checked_packet_0 <= candidate[46:0];
                        checked_packet_1 <= candidate[93:47];
                        checked_packet_2 <= candidate[140:94];
                        checked_packet_3 <= candidate[187:141];
                        checked_packet_4 <= candidate[234:188];
                        checked_packet_5 <= candidate[281:235];
                        checked_packet_6 <= candidate[328:282];
                        checked_packet_7 <= candidate[375:329];
                        checking<=1;crc_index<=0;crc<=0;
                    end
                end
            end
        end
endmodule
`default_nettype wire
