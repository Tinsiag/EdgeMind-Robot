`timescale 1ns/1ps
module camera_pads_tb;
 reg [9:0] stimulus=0;wire [9:0] observed;integer i;
 a745_camera_pads dut(.vsync(stimulus[9]),.href(stimulus[8]),.data(stimulus[7:0]),
  .vsync_d(observed[9]),.href_d(observed[8]),.data_d(observed[7:0]));
 initial begin
  #20;stimulus=10'h3ff;#5;
  for(i=0;i<1024;i=i+1) begin
   stimulus=i;#5;
   if(observed!==stimulus) $fatal(1,"DVP pad alignment %h != %h",observed,stimulus);
  end
  $display("PASS camera pads: manufacturer IODELAY, all 1024 data/HREF/VS combinations aligned");$finish;
 end
endmodule
