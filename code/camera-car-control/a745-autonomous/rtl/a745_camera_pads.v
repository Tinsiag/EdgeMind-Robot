`timescale 1ns/1ps
`default_nettype none
// Delay the complete source-synchronous bundle equally before its input FFs.
// C_STATIC_DLY is a device tap setting. Signoff uses the placed fast/slow
// timing model, never the nominal ps/tap value. PCLK itself is undelayed.
module a745_camera_pads(input wire vsync,href,input wire [7:0] data,
 output wire vsync_d,href_d,output wire [7:0] data_d);
 wire [9:0] incoming={vsync,href,data};wire [9:0] delayed;
 genvar i;
 generate for(i=0;i<10;i=i+1) begin: pads
  IODELAY #(.C_STATIC_DLY(96),.DYN_DLY_EN("FALSE"),.ADAPT_EN("FALSE")) delay(
   .DI(incoming[i]),.DO(delayed[i]),.DF(),.DLYSTEP(8'd0),.SDTAP(1'b0),.VALUE(1'b0));
 end endgenerate
 assign {vsync_d,href_d,data_d}=delayed;
endmodule
`default_nettype wire
