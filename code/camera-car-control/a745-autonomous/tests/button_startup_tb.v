`timescale 1us/1ns
module button_startup_tb;
 reg clk=0;always #0.5 clk=~clk;
 reg rst_n=0,button_n=1;wire press;integer events=0;
 a741_button_debounce #(.CLK_HZ(1000000),.DEBOUNCE_MS(2)) dut(.*);
 always @(posedge clk) if(press)events=events+1;
 initial begin
  #3;rst_n=1;#3000;button_n=0;#3000;
  if(events!=1)$fatal(1,"first released-start press ignored");
  #5000;if(events!=1)$fatal(1,"held repeated");
  rst_n=0;#3;rst_n=1;#3000;
  if(events!=1)$fatal(1,"held startup event");
  button_n=1;#3000;button_n=0;#3000;
  if(events!=2)$fatal(1,"release then press missing");
  $display("PASS normal/held startup, release qualification and single event");$finish;
 end
endmodule
