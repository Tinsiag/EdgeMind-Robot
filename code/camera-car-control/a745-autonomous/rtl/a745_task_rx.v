`timescale 1ns/1ps
`default_nettype none
// ET10 is separate from ED10. Only an already locally armed mode3 session
// accepts bounded motion intents. The upstream MAC checks entire-frame FCS.
module a745_task_rx(
 input wire clk,rst_n,ms_tick,input wire [7:0] data,input wire valid,last,user,
 output wire ready,input wire session_valid,input wire [31:0] session_id,video_frame,
 output wire fresh,output reg [2:0] action,output reg [7:0] accepted,
 output reg [31:0] config_id,last_sequence
);
 reg [7:0] length;reg [1:0] state;reg bad,have_sequence,expired;
 reg [23:0] ip_sum,udp_sum;reg [7:0] high_byte;
 reg [383:0] payload;reg [15:0] checksum;
 reg [31:0] accepted_session,host_nonce,last_frame;
 reg [9:0] age,video_age;reg [15:0] ttl,source_age;
 wire [31:0] sequence_delta=payload[63:32]-last_sequence;
 wire [31:0] frame_delta=video_frame-payload[127:96];
 wire [23:0] udp_total=udp_sum+24'h18166+56;
 wire [16:0] ip_fold={1'b0,ip_sum[15:0]}+ip_sum[23:16];
 wire [16:0] udp_fold={1'b0,udp_total[15:0]}+udp_total[23:16];
 wire ip_ok=({1'b0,ip_fold[15:0]}+ip_fold[16])==17'hffff;
 wire udp_ok=({1'b0,udp_fold[15:0]}+udp_fold[16])==17'hffff;
 reg header_bad;
 always @*begin header_bad=0;case(length)
  0,5:header_bad=data!=2;
  1,2,3,4,10,21,28,32:header_bad=data!=0;
  6:header_bad=data!=8'h48;7:header_bad=data!=8'hda;8:header_bad=data!=8'h35;9:header_bad=data!=8'h60;11:header_bad=data!=8'h99;
  12:header_bad=data!=8'h08;13:header_bad=data!=0;14:header_bad=data!=8'h45;
  16,38:header_bad=data!=0;17:header_bad=data!=76;39:header_bad=data!=56;
  20:header_bad=(data&8'hbf)!=0;23:header_bad=data!=17;
  26,30:header_bad=data!=192;27,31:header_bad=data!=168;29:header_bad=data!=3;33:header_bad=data!=2;
  34,36:header_bad=data!=8'h17;35,37:header_bad=data!=8'hda;
 endcase end
 assign ready=state==0;
 assign fresh=session_valid && have_sequence && !expired && accepted_session==session_id && age<ttl && video_age<600 &&
  (action==0 || {1'b0,age}+{1'b0,source_age}<600);
 always @(posedge clk or negedge rst_n)
 if(!rst_n)begin
  state<=0;length<=0;bad<=0;have_sequence<=0;expired<=0;ip_sum<=0;udp_sum<=0;high_byte<=0;payload<=0;checksum<=0;
  accepted_session<=0;host_nonce<=0;last_sequence<=0;config_id<=0;age<=1000;video_age<=1000;last_frame<=0;ttl<=0;source_age<=0;action<=0;accepted<=0;
 end else begin
  if(ms_tick)begin if(age<1000)age<=age+1'b1;if(video_age<1000)video_age<=video_age+1'b1;end
  if(video_frame!=last_frame)begin video_age<=0;last_frame<=video_frame;end
  if(have_sequence && (age>=ttl || video_age>=600))expired<=1;
  if(!session_valid || accepted_session!=session_id)begin have_sequence<=0;action<=0;expired<=0;end
  case(state)
   0:if(valid)begin
    bad<=bad|header_bad|user|(length>=90);
    if(!length[0])high_byte<=data;
    if(length>=14 && length<34 && length[0])ip_sum<=ip_sum+{high_byte,data};
    if(length>=34 && length<90 && length[0])udp_sum<=udp_sum+{high_byte,data};
    if(length==40)checksum[15:8]<=data;if(length==41)checksum[7:0]<=data;
    if(length>=42 && length<90)payload<={data,payload[383:8]};
    if(last)state<=1;else if(length!=255)length<=length+1'b1;
   end
   1:begin
    state<=2;
    if(session_valid && !expired && !bad && length==89 && ip_ok && udp_ok && checksum!=0 &&
       payload[31:0]==32'h30315445 && payload[95:64]==session_id && payload[167:160]<=5 &&
       payload[175:168]<80 && payload[183:176]<=3 && payload[287:272]==0 && payload[383:320]==0 &&
       payload[239:224]>=100 && payload[239:224]<=500 && (payload[167:160]==0 || payload[255:240]<=600) && payload[271:256]<=200 &&
       (!have_sequence || (sequence_delta!=0 && !sequence_delta[31] && payload[319:288]==host_nonce &&
        (payload[159:128]==config_id || payload[167:160]==0))) &&
       (payload[167:160]==0 || (frame_delta<=18 && video_age<600 && payload[127:96]!=0)) &&
       (payload[167:160]!=1 && payload[167:160]!=4 ||
        (payload[183:176]==3 && payload[191:184]>=128 && payload[223:208]>=100 && payload[223:208]<=10000) ||
        (payload[167:160]==1 && payload[183:176]==1 && payload[223:208]>800)) &&
       (payload[167:160]!=1 || payload[207:192]<=1500 || payload[207:192]>=64036) &&
       (payload[167:160]!=4 || payload[223:208]>=450 && payload[223:208]<=600))begin
     accepted_session<=session_id;host_nonce<=payload[319:288];have_sequence<=1;last_sequence<=payload[63:32];
     config_id<=payload[159:128];ttl<=payload[239:224];source_age<=payload[255:240];age<=0;action<=payload[162:160];accepted<=accepted+1'b1;
    end
   end
   2:begin state<=0;length<=0;bad<=0;ip_sum<=0;udp_sum<=0;checksum<=0;end
  endcase
 end
endmodule
`default_nettype wire
