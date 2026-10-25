`timescale 1ns/1ps
`default_nettype none
// LD06: 54 2c, speed, start-angle, 12*(distance,confidence), end-angle,
// device timestamp, CRC8(poly 4d). Stream only packets that passed CRC.
module ld06_parser #(parameter STALE_MS=300)(
    input wire clk,rst_n,ms_tick,byte_valid,framing_error,input wire [7:0] data,
    output reg packet_valid,valid,point_valid,
    output reg [15:0] angle_cdeg,distance_mm,
    output reg [7:0] confidence,
    output reg [375:0] packet,
    output reg [31:0] sample_time,sequence_id,errors,dropped,
    output reg [15:0] front_mm,left_mm,right_mm
);
    reg [375:0] window,candidate,checked_packet;
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
    reg [15:0] last_step,gap_angle;
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
            checked_packet<=0;checking<=0;crc_index<=0;crc<=0;interpolation_ready<=0;divide_start<=0;
            point_step<=0;point_remainder<=0;point_offset<=0;residue<=0;
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
                gap_angle=p_angle>=last_angle ? p_angle-last_angle:p_angle+36000-last_angle;
                if(point_index==0 && have_last && gap_angle>(last_step*3>100 ? last_step*3:100)) begin
                    front_mm<=65535;left_mm<=65535;right_mm<=65535;scan_started<=0;
                    scan_front<=65535;scan_left<=65535;scan_right<=65535;dropped<=dropped+1'b1;
                end else if(have_last && p_angle+18000<last_angle) begin
                    if(scan_started) begin front_mm<=scan_front;left_mm<=scan_left;right_mm<=scan_right;end
                    scan_front<=p_conf>=10 && p_dist>0 ? p_dist:65535;
                    scan_left<=65535;scan_right<=65535;scan_started<=1;
                end else if(p_conf>=10 && p_dist>0) begin
                    if((p_angle<=3000 || p_angle>=33000) && p_dist<scan_front) scan_front<=p_dist;
                    if(p_angle>=4500 && p_angle<=13500 && p_dist<scan_left) scan_left<=p_dist;
                    if(p_angle>=22500 && p_angle<=31500 && p_dist<scan_right) scan_right<=p_dist;
                end
                last_angle<=p_angle;have_last<=1;
                if(point_index==11) begin emitting<=0;interpolation_ready<=0;end
                else begin
                    point_index<=point_index+1'b1;
                    if(residue+point_remainder>=11) begin
                        point_offset<=point_offset+point_step+1'b1;residue<=residue+point_remainder-11;
                    end else begin point_offset<=point_offset+point_step;residue<=residue+point_remainder;end
                end
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
                checking<=0;emitting<=0;interpolation_ready<=0;valid<=0;
                front_mm<=65535;left_mm<=65535;right_mm<=65535;
            end
            else if(byte_valid) begin
                candidate={data,window[375:8]};window<=candidate;
                if(filled<47) filled<=filled+1'b1;
                // A validated packet's payload cannot start another packet.
                if(packet_guard!=0) packet_guard<=packet_guard-1'b1;
                else if(filled>=46 && candidate[15:0]==16'h2c54) begin
                    if(checking) dropped<=dropped+1'b1;
                    else begin checked_packet<=candidate;checking<=1;crc_index<=0;crc<=0;end
                end
            end
        end
endmodule
`default_nettype wire
