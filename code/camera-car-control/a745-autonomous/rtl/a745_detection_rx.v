`timescale 1ns/1ps
`default_nettype none
// Streaming display-only decoder. FCS is checked by the upstream frame MAC.
// No packet RAM: at most one 12-byte record is assembled at a time.
module a745_detection_rx #(parameter SESSION_CYCLES=250000000)(
 input wire clk,rst_n,input wire [7:0] data,input wire valid,last,user,
 output wire ready,input wire update_ready,output reg update,
 output reg [771:0] detections,output reg [7:0] accepted
);
 reg [8:0] length,frame_length;
 reg bad;
 reg [1:0] state;
 reg [23:0] ip_sum,udp_sum;
 reg [7:0] high_byte;
 reg [15:0] ip_length,udp_length,udp_checksum;
 reg [3:0] count,record_byte,record_index;
 reg [95:0] record;
 reg [767:0] candidate_boxes;
 reg [31:0] packet_sequence,last_sequence;
 reg have_sequence;
 reg [27:0] age;
 wire [31:0] sequence_delta=packet_sequence-last_sequence;
 wire [23:0] udp_total=udp_sum+24'h18166+udp_length;
 wire [16:0] ip_fold={1'b0,ip_sum[15:0]}+ip_sum[23:16];
 wire [16:0] udp_fold={1'b0,udp_total[15:0]}+udp_total[23:16];
 wire ip_ok=({1'b0,ip_fold[15:0]}+ip_fold[16])==17'hffff;
 wire udp_ok=({1'b0,udp_fold[15:0]}+udp_fold[16])==17'hffff;
 wire [95:0] complete_record={data,record[95:8]};
 wire [15:0] x1=complete_record[15:0],y1=complete_record[31:16];
 wire [15:0] x2=complete_record[47:32],y2=complete_record[63:48];
 wire record_bad=(x1>=x2 || y1>=y2 || x2>=640 || y2>=480 ||
     complete_record[71:64]>=80 || complete_record[79:72]==0 || complete_record[95:80]!=0);
 reg header_bad;
 reg [7:0] expected_udp;
 integer bi;
 always @* begin
  case(count)
   0:expected_udp=24;1:expected_udp=36;2:expected_udp=48;3:expected_udp=60;
   4:expected_udp=72;5:expected_udp=84;6:expected_udp=96;7:expected_udp=108;
   8:expected_udp=120;default:expected_udp=0;
  endcase
 end
 assign ready=state==0;
 always @* begin
  header_bad=0;
  case(length)
   0,5:header_bad=data!=2;
   1,2,3,4,10,21,28,32,51,56,57:header_bad=data!=0;
   6:header_bad=data!=8'h48;
   7:header_bad=data!=8'hda;
   8:header_bad=data!=8'h35;
   9:header_bad=data!=8'h60;
   11:header_bad=data!=8'h99;
   12:header_bad=data!=8'h08;
   13:header_bad=data!=0;
   14:header_bad=data!=8'h45;
   20:header_bad=(data&8'hbf)!=0;
   23:header_bad=data!=17;
   26,30:header_bad=data!=192;
   27,31:header_bad=data!=168;
   29:header_bad=data!=3;
   33:header_bad=data!=2;
   34,36:header_bad=data!=8'h17;
   35,37:header_bad=data!=8'hd9;
   42:header_bad=data!="E";
   43:header_bad=data!="D";
   44:header_bad=data!="1";
   45:header_bad=data!="0";
   50:header_bad=data>8;
   52:header_bad=data!=8'h80;
   53:header_bad=data!=2;
   54:header_bad=data!=8'he0;
   55:header_bad=data!=1;
  endcase
 end
 always @(posedge clk or negedge rst_n)
 if(!rst_n) begin
  state<=0;length<=0;frame_length<=0;bad<=0;ip_sum<=0;udp_sum<=0;high_byte<=0;
  ip_length<=0;udp_length<=0;udp_checksum<=0;count<=0;record_byte<=0;record_index<=0;
  record<=0;candidate_boxes<=0;packet_sequence<=0;last_sequence<=0;have_sequence<=0;age<=0;
  update<=0;detections<=0;accepted<=0;
 end else begin
  update<=0;
  if(age<SESSION_CYCLES) age<=age+1'b1;else have_sequence<=0;
  case(state)
   0: if(valid) begin
    bad<=bad|header_bad|user|(length>=160);
    if(!length[0])high_byte<=data;
    if(length>=14 && length<34 && length[0])ip_sum<=ip_sum+{high_byte,data};
    if(length>=34 && (length<40 || length<34+udp_length) && length[0])udp_sum<=udp_sum+{high_byte,data};
    case(length)
     16:ip_length[15:8]<=data;
     17:ip_length[7:0]<=data;
     38:udp_length[15:8]<=data;
     39:udp_length[7:0]<=data;
     40:udp_checksum[15:8]<=data;
     41:udp_checksum[7:0]<=data;
     46:packet_sequence[7:0]<=data;
     47:packet_sequence[15:8]<=data;
     48:packet_sequence[23:16]<=data;
     49:packet_sequence[31:24]<=data;
     50:count<=data[3:0];
    endcase
    if(length>=58 && record_index<count && record_index<8)begin
     record<=complete_record;
     if(record_byte==11)begin
      record_byte<=0;record_index<=record_index+1'b1;
      if(record_bad)bad<=1;
      for(bi=0;bi<8;bi=bi+1)
       if(record_index==bi)candidate_boxes[bi*96+:96]<=complete_record;
     end else record_byte<=record_byte+1'b1;
    end
    if(last)begin state<=1;frame_length<=length+1'b1;end
    else if(length<511)length<=length+1'b1;
   end
   1:begin
    state<=3;
    if(!bad && count<=8 && ip_length==20+expected_udp && udp_length==expected_udp &&
       frame_length==((count==0)?60:34+expected_udp) && record_index==count && record_byte==0 &&
       udp_checksum!=0 && ip_ok && udp_ok &&
       (!have_sequence || (sequence_delta!=0 && !sequence_delta[31])))begin
     state<=2;
    end
   end
   2:begin
    detections<={candidate_boxes,count};
    if(update_ready)begin update<=1;accepted<=accepted+1'b1;
     last_sequence<=packet_sequence;have_sequence<=1;age<=0;end
    state<=3;
   end
   3:begin
    state<=0;length<=0;bad<=0;ip_sum<=0;udp_sum<=0;
    record_byte<=0;record_index<=0;candidate_boxes<=0;
   end
  endcase
 end
endmodule
`default_nettype wire
