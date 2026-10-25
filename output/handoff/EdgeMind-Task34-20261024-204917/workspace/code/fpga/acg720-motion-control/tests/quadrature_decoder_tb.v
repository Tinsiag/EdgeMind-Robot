`timescale 1ns/1ps
module quadrature_decoder_tb;
    reg clk=0, rstn=0, a=0, b=0; wire signed [1:0] step; wire invalid;
    always #5 clk=~clk;
    quadrature_decoder dut(.clk(clk),.rstn(rstn),.a(a),.b(b),.invert(1'b0),.step(step),.invalid(invalid));
    task phase(input reg na,input reg nb); begin @(negedge clk); a=na; b=nb; repeat(4) @(posedge clk); end endtask
    integer pos, neg, bad;
    always @(posedge clk) begin if(step==1) pos=pos+1; if(step==-1) neg=neg+1; if(invalid) bad=bad+1; end
    initial begin pos=0;neg=0;bad=0; #20; rstn=1; repeat(8) @(negedge clk);
        phase(0,1); phase(1,1); phase(1,0); phase(0,0);
        phase(1,1); phase(0,1); phase(0,0); phase(1,0);
        phase(1,1); phase(0,0);
        #20; if(pos!=4 || neg!=4 || bad==0) $fatal(1,"quadrature failure pos=%0d neg=%0d bad=%0d",pos,neg,bad);
        $display("PASS quadrature pos=%0d neg=%0d invalid=%0d",pos,neg,bad); $finish;
    end
endmodule
