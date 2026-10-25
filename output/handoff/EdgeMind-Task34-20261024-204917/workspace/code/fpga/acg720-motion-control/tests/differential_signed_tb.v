`timescale 1ns/1ps
module differential_signed_tb;
 reg signed [31:0] v=0;reg signed [15:0] omega=0;
 wire signed [31:0] l,r;
 differential_drive dut(.v_mm_s(v),.omega_mrad_s(omega),.wheel_base_mm(16'd121),.max_speed_mm_s(32'd100),.left_speed(l),.right_speed(r));
 initial begin
  v=-50;#10;if(l!=-50||r!=-50) $fatal(1,"Backward sign");
  v=-500;#10;if(l!=-100||r!=-100) $fatal(1,"Negative saturation");
  v=500;#10;if(l!=100||r!=100) $fatal(1,"Positive saturation");
  v=0;omega=-1000;#10;if(l<=0||r>=0) $fatal(1,"Negative angular sign %0d %0d",l,r);
  omega=1000;#10;if(l>=0||r<=0) $fatal(1,"Positive angular sign");
  $display("PASS differential signed backward, angular directions and limits");$finish;
 end
endmodule
