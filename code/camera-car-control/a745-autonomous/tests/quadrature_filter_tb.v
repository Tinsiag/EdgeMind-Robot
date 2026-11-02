`timescale 1ns/1ps
module quadrature_filter_tb;
 reg clk=0;always #10 clk=~clk;
 reg rstn=0,a=1,b=1,invert=0;
 wire signed [1:0] step;wire invalid;
 integer total=0,edges=0,bad=0,width;
 quadrature_decoder dut(.*);
 always @(negedge clk) if(rstn) begin
  total=total+$signed(step);edges=edges+(step!=0);bad=bad+invalid;
 end
 task hold_ab(input [1:0] ab,input integer clocks);
  begin {a,b}=ab;repeat(clocks) @(negedge clk);end
 endtask
 task clear_measurement;
  begin @(posedge clk);#1;total=0;edges=0;bad=0;end
 endtask
 initial begin
  repeat(4) @(negedge clk);rstn=1;repeat(120) @(negedge clk);
  if(total || edges || bad) $fatal(1,"nonzero startup AB generated a fictitious edge");
  // Common-mode and single-wire spikes shorter than 2 us must not create
  // a count, an illegal transition, or a direction reversal at 50 MHz.
  for(width=1;width<100;width=width+1) begin
   hold_ab(2'b00,width);hold_ab(2'b11,120);
   hold_ab(2'b01,width);hold_ab(2'b11,120);
   if(total || edges || bad) $fatal(1,"short encoder spike was decoded: width=%0d count=%0d edges=%0d illegal=%0d",width,total,edges,bad);
  end
  hold_ab(2'b10,100);hold_ab(2'b11,120);
  if(total || edges!=2 || bad) $fatal(1,"exact 100-sample qualification boundary");
  clear_measurement;
  // Every state is stable beyond the filter bound. Keep true x4 counts,
  // including direction inversion and reversals.
  hold_ab(2'b10,120);hold_ab(2'b00,120);hold_ab(2'b01,120);hold_ab(2'b11,120);
  if(total!=4 || edges!=4 || bad) $fatal(1,"clean forward x4 cycle lost");
  invert=1;clear_measurement;
  hold_ab(2'b10,120);hold_ab(2'b00,120);hold_ab(2'b01,120);hold_ab(2'b11,120);
  if(total!=-4 || edges!=4 || bad) $fatal(1,"inverted x4 cycle lost");
  invert=0;clear_measurement;
  hold_ab(2'b01,120);hold_ab(2'b00,120);hold_ab(2'b10,120);hold_ab(2'b11,120);
  if(total!=-4 || edges!=4 || bad) $fatal(1,"reverse x4 cycle lost");
  clear_measurement;
  hold_ab(2'b00,120);hold_ab(2'b11,120);
  if(total || edges || bad!=2) $fatal(1,"stable illegal AB transitions were hidden or miscounted");
  // Qualification is restarted by every different candidate. Several
  // short states cannot combine into one accepted state.
  clear_measurement;
  repeat(20) begin hold_ab(2'b00,20);hold_ab(2'b01,20);hold_ab(2'b10,20);hold_ab(2'b11,20);end
  hold_ab(2'b11,120);
  if(total || edges || bad) $fatal(1,"different short candidates accumulated qualification");
  $display("PASS encoder filter: startup AB, 1..99-cycle single/common spikes, clean forward/reverse/invert x4, stable illegal transitions and candidate restart");$finish;
 end
 initial begin #3000000;$fatal(1,"quadrature filter watchdog");end
endmodule
