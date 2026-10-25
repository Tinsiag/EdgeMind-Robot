`timescale 1ns/1ps
module encoder_startup_tb;
    reg clk=0,rstn=0,a=0,b=0;
    wire signed [1:0] step;wire invalid;
    integer n,steps=0,bad=0;
    always #5 clk=~clk;
    quadrature_decoder dut(.clk(clk),.rstn(rstn),.a(a),.b(b),.invert(1'b0),.step(step),.invalid(invalid));
    always @(posedge clk) if(rstn) begin
        if(step!=0) steps=steps+1;
        if(invalid) bad=bad+1;
    end
    task phase;
        input [1:0] ab;
        begin @(negedge clk);{a,b}=ab;repeat(8) @(negedge clk);end
    endtask
    initial begin
        for(n=0;n<4;n=n+1) begin
            @(negedge clk);rstn=0;{a,b}=n[1:0];steps=0;bad=0;
            repeat(6) @(negedge clk);rstn=1;
            repeat(20) @(negedge clk);
            if(steps!=0||bad!=0) $fatal(1,"Startup AB=%b steps=%0d invalid=%0d",n[1:0],steps,bad);
        end
        // Last startup state is 11; a real 11 -> 00 jump must still be detected.
        phase(0);
        if(bad!=1) $fatal(1,"Real invalid jump not detected: %0d",bad);
        phase(1);phase(3);phase(2);phase(0);
        if(steps!=4) $fatal(1,"Normal transitions lost: %0d",steps);
        $display("PASS startup all four AB states: zero phantom counts/faults; real invalid jump retained");$finish;
    end
    initial begin #20000;$fatal(1,"Startup watchdog");end
endmodule
