`timescale 1ns/1ps
`default_nettype none
// Generated CAD path guards; see generate_path_envelope.py.
module a745_path_envelope(input wire [6:0] bin,output reg [9:0] advance_limit,reverse_limit,left_exit_limit,right_exit_limit,spin_limit);
always @* begin
 advance_limit=1023;
 reverse_limit=1023;
 left_exit_limit=1023;
 right_exit_limit=1023;
 spin_limit=1023;
 case(bin)
  7'd0:begin advance_limit=10'd266;reverse_limit=10'd105;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd158;end
  7'd1:begin advance_limit=10'd269;reverse_limit=10'd106;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd159;end
  7'd2:begin advance_limit=10'd274;reverse_limit=10'd108;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd160;end
  7'd3:begin advance_limit=10'd281;reverse_limit=10'd111;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd162;end
  7'd4:begin advance_limit=10'd292;reverse_limit=10'd115;left_exit_limit=10'd16;right_exit_limit=10'd16;spin_limit=10'd165;end
  7'd5:begin advance_limit=10'd305;reverse_limit=10'd120;left_exit_limit=10'd16;right_exit_limit=10'd16;spin_limit=10'd169;end
  7'd6:begin advance_limit=10'd318;reverse_limit=10'd127;left_exit_limit=10'd17;right_exit_limit=10'd17;spin_limit=10'd173;end
  7'd7:begin advance_limit=10'd309;reverse_limit=10'd136;left_exit_limit=10'd18;right_exit_limit=10'd18;spin_limit=10'd178;end
  7'd8:begin advance_limit=10'd276;reverse_limit=10'd147;left_exit_limit=10'd19;right_exit_limit=10'd19;spin_limit=10'd184;end
  7'd9:begin advance_limit=10'd251;reverse_limit=10'd161;left_exit_limit=10'd21;right_exit_limit=10'd21;spin_limit=10'd190;end
  7'd10:begin advance_limit=10'd232;reverse_limit=10'd180;left_exit_limit=10'd23;right_exit_limit=10'd23;spin_limit=10'd198;end
  7'd11:begin advance_limit=10'd217;reverse_limit=10'd206;left_exit_limit=10'd26;right_exit_limit=10'd26;spin_limit=10'd206;end
  7'd12:begin advance_limit=10'd206;reverse_limit=10'd206;left_exit_limit=10'd31;right_exit_limit=10'd31;spin_limit=10'd215;end
  7'd13:begin advance_limit=10'd197;reverse_limit=10'd197;left_exit_limit=10'd38;right_exit_limit=10'd38;spin_limit=10'd226;end
  7'd14:begin advance_limit=10'd190;reverse_limit=10'd190;left_exit_limit=10'd49;right_exit_limit=10'd49;spin_limit=10'd237;end
  7'd15:begin advance_limit=10'd185;reverse_limit=10'd185;left_exit_limit=10'd72;right_exit_limit=10'd72;spin_limit=10'd249;end
  7'd16:begin advance_limit=10'd181;reverse_limit=10'd181;left_exit_limit=10'd140;right_exit_limit=10'd118;spin_limit=10'd262;end
  7'd17:begin advance_limit=10'd179;reverse_limit=10'd179;left_exit_limit=10'd469;right_exit_limit=10'd118;spin_limit=10'd276;end
  7'd18:begin advance_limit=10'd179;reverse_limit=10'd179;left_exit_limit=10'd470;right_exit_limit=10'd118;spin_limit=10'd291;end
  7'd19:begin advance_limit=10'd181;reverse_limit=10'd181;left_exit_limit=10'd476;right_exit_limit=10'd119;spin_limit=10'd306;end
  7'd20:begin advance_limit=10'd185;reverse_limit=10'd185;left_exit_limit=10'd485;right_exit_limit=10'd122;spin_limit=10'd322;end
  7'd21:begin advance_limit=10'd190;reverse_limit=10'd190;left_exit_limit=10'd498;right_exit_limit=10'd125;spin_limit=10'd338;end
  7'd22:begin advance_limit=10'd197;reverse_limit=10'd197;left_exit_limit=10'd517;right_exit_limit=10'd129;spin_limit=10'd354;end
  7'd23:begin advance_limit=10'd206;reverse_limit=10'd206;left_exit_limit=10'd541;right_exit_limit=10'd135;spin_limit=10'd370;end
  7'd24:begin advance_limit=10'd217;reverse_limit=10'd217;left_exit_limit=10'd571;right_exit_limit=10'd143;spin_limit=10'd386;end
  7'd25:begin advance_limit=10'd232;reverse_limit=10'd232;left_exit_limit=10'd579;right_exit_limit=10'd153;spin_limit=10'd401;end
  7'd26:begin advance_limit=10'd251;reverse_limit=10'd251;left_exit_limit=10'd531;right_exit_limit=10'd165;spin_limit=10'd416;end
  7'd27:begin advance_limit=10'd276;reverse_limit=10'd276;left_exit_limit=10'd483;right_exit_limit=10'd181;spin_limit=10'd429;end
  7'd28:begin advance_limit=10'd309;reverse_limit=10'd309;left_exit_limit=10'd446;right_exit_limit=10'd203;spin_limit=10'd442;end
  7'd29:begin advance_limit=10'd332;reverse_limit=10'd355;left_exit_limit=10'd418;right_exit_limit=10'd233;spin_limit=10'd453;end
  7'd30:begin advance_limit=10'd325;reverse_limit=10'd419;left_exit_limit=10'd395;right_exit_limit=10'd275;spin_limit=10'd462;end
  7'd31:begin advance_limit=10'd310;reverse_limit=10'd420;left_exit_limit=10'd378;right_exit_limit=10'd339;spin_limit=10'd471;end
  7'd32:begin advance_limit=10'd299;reverse_limit=10'd406;left_exit_limit=10'd364;right_exit_limit=10'd361;spin_limit=10'd477;end
  7'd33:begin advance_limit=10'd291;reverse_limit=10'd395;left_exit_limit=10'd354;right_exit_limit=10'd354;spin_limit=10'd482;end
  7'd34:begin advance_limit=10'd286;reverse_limit=10'd387;left_exit_limit=10'd348;right_exit_limit=10'd348;spin_limit=10'd485;end
  7'd35:begin advance_limit=10'd283;reverse_limit=10'd383;left_exit_limit=10'd344;right_exit_limit=10'd344;spin_limit=10'd485;end
  7'd36:begin advance_limit=10'd283;reverse_limit=10'd383;left_exit_limit=10'd344;right_exit_limit=10'd344;spin_limit=10'd485;end
  7'd37:begin advance_limit=10'd286;reverse_limit=10'd387;left_exit_limit=10'd348;right_exit_limit=10'd348;spin_limit=10'd485;end
  7'd38:begin advance_limit=10'd291;reverse_limit=10'd395;left_exit_limit=10'd354;right_exit_limit=10'd354;spin_limit=10'd482;end
  7'd39:begin advance_limit=10'd299;reverse_limit=10'd406;left_exit_limit=10'd361;right_exit_limit=10'd364;spin_limit=10'd477;end
  7'd40:begin advance_limit=10'd310;reverse_limit=10'd420;left_exit_limit=10'd339;right_exit_limit=10'd378;spin_limit=10'd471;end
  7'd41:begin advance_limit=10'd325;reverse_limit=10'd419;left_exit_limit=10'd275;right_exit_limit=10'd395;spin_limit=10'd462;end
  7'd42:begin advance_limit=10'd332;reverse_limit=10'd354;left_exit_limit=10'd232;right_exit_limit=10'd418;spin_limit=10'd453;end
  7'd43:begin advance_limit=10'd309;reverse_limit=10'd309;left_exit_limit=10'd203;right_exit_limit=10'd446;spin_limit=10'd442;end
  7'd44:begin advance_limit=10'd276;reverse_limit=10'd276;left_exit_limit=10'd181;right_exit_limit=10'd483;spin_limit=10'd429;end
  7'd45:begin advance_limit=10'd251;reverse_limit=10'd251;left_exit_limit=10'd165;right_exit_limit=10'd531;spin_limit=10'd416;end
  7'd46:begin advance_limit=10'd232;reverse_limit=10'd232;left_exit_limit=10'd153;right_exit_limit=10'd579;spin_limit=10'd401;end
  7'd47:begin advance_limit=10'd217;reverse_limit=10'd217;left_exit_limit=10'd143;right_exit_limit=10'd571;spin_limit=10'd386;end
  7'd48:begin advance_limit=10'd206;reverse_limit=10'd206;left_exit_limit=10'd135;right_exit_limit=10'd541;spin_limit=10'd370;end
  7'd49:begin advance_limit=10'd197;reverse_limit=10'd197;left_exit_limit=10'd129;right_exit_limit=10'd517;spin_limit=10'd354;end
  7'd50:begin advance_limit=10'd190;reverse_limit=10'd190;left_exit_limit=10'd125;right_exit_limit=10'd498;spin_limit=10'd338;end
  7'd51:begin advance_limit=10'd185;reverse_limit=10'd185;left_exit_limit=10'd122;right_exit_limit=10'd485;spin_limit=10'd322;end
  7'd52:begin advance_limit=10'd181;reverse_limit=10'd181;left_exit_limit=10'd119;right_exit_limit=10'd476;spin_limit=10'd306;end
  7'd53:begin advance_limit=10'd179;reverse_limit=10'd179;left_exit_limit=10'd118;right_exit_limit=10'd470;spin_limit=10'd291;end
  7'd54:begin advance_limit=10'd179;reverse_limit=10'd179;left_exit_limit=10'd118;right_exit_limit=10'd469;spin_limit=10'd276;end
  7'd55:begin advance_limit=10'd181;reverse_limit=10'd181;left_exit_limit=10'd118;right_exit_limit=10'd140;spin_limit=10'd262;end
  7'd56:begin advance_limit=10'd185;reverse_limit=10'd185;left_exit_limit=10'd72;right_exit_limit=10'd72;spin_limit=10'd249;end
  7'd57:begin advance_limit=10'd190;reverse_limit=10'd190;left_exit_limit=10'd49;right_exit_limit=10'd49;spin_limit=10'd237;end
  7'd58:begin advance_limit=10'd197;reverse_limit=10'd197;left_exit_limit=10'd38;right_exit_limit=10'd38;spin_limit=10'd226;end
  7'd59:begin advance_limit=10'd206;reverse_limit=10'd206;left_exit_limit=10'd31;right_exit_limit=10'd31;spin_limit=10'd215;end
  7'd60:begin advance_limit=10'd217;reverse_limit=10'd206;left_exit_limit=10'd26;right_exit_limit=10'd26;spin_limit=10'd206;end
  7'd61:begin advance_limit=10'd232;reverse_limit=10'd180;left_exit_limit=10'd23;right_exit_limit=10'd23;spin_limit=10'd198;end
  7'd62:begin advance_limit=10'd251;reverse_limit=10'd161;left_exit_limit=10'd21;right_exit_limit=10'd21;spin_limit=10'd190;end
  7'd63:begin advance_limit=10'd276;reverse_limit=10'd147;left_exit_limit=10'd19;right_exit_limit=10'd19;spin_limit=10'd184;end
  7'd64:begin advance_limit=10'd309;reverse_limit=10'd136;left_exit_limit=10'd18;right_exit_limit=10'd18;spin_limit=10'd178;end
  7'd65:begin advance_limit=10'd318;reverse_limit=10'd127;left_exit_limit=10'd17;right_exit_limit=10'd17;spin_limit=10'd173;end
  7'd66:begin advance_limit=10'd305;reverse_limit=10'd120;left_exit_limit=10'd16;right_exit_limit=10'd16;spin_limit=10'd169;end
  7'd67:begin advance_limit=10'd292;reverse_limit=10'd115;left_exit_limit=10'd16;right_exit_limit=10'd16;spin_limit=10'd165;end
  7'd68:begin advance_limit=10'd281;reverse_limit=10'd111;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd162;end
  7'd69:begin advance_limit=10'd274;reverse_limit=10'd108;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd160;end
  7'd70:begin advance_limit=10'd269;reverse_limit=10'd106;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd159;end
  7'd71:begin advance_limit=10'd266;reverse_limit=10'd105;left_exit_limit=10'd15;right_exit_limit=10'd15;spin_limit=10'd158;end
 default:begin end
 endcase
end
endmodule
`default_nettype wire
