`timescale 1ns/1ps
module sincos_equivalence_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0;reg [15:0] angle=0;
    wire busy,done;wire signed [17:0] cosine,sine;
    a741_sincos dut(.*);
    integer n,j,x,y,z,nx,ny,a,negative,largest=0;
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        for(n=0;n<65536;n=n+1) begin
            angle=n;z=n<32768 ? n:n-65536;negative=0;
            if(z>16384) begin z=z-32768;negative=1;end
            else if(z< -16384) begin z=z+32768;negative=1;end
            x=19898;y=0;
            for(j=0;j<15;j=j+1) begin
                case(j)
                    0:a=8192;1:a=4836;2:a=2555;3:a=1297;4:a=651;5:a=326;
                    6:a=163;7:a=81;8:a=41;9:a=20;10:a=10;11:a=5;12:a=3;default:a=1;
                endcase
                nx=z>=0 ? x-(y>>>j):x+(y>>>j);ny=z>=0 ? y+(x>>>j):y-(x>>>j);
                z=z>=0 ? z-a:z+a;x=nx;y=ny;
                if(x>largest) largest=x;if(-x>largest) largest=-x;
                if(y>largest) largest=y;if(-y>largest) largest=-y;
                if(x< -131072 || x>131071 || y< -131072 || y>131071 || z< -65536 || z>65535)
                    $fatal(1,"CORDIC intermediate overflow");
            end
            start=1;@(negedge clk);start=0;
            if(!busy) $fatal(1,"start not accepted");
            repeat(15) @(negedge clk);
            if(!done || busy || cosine!==(negative ? -x:x) || sine!==(negative ? -y:y))
                $fatal(1,"angle=%0d got=%0d/%0d expected=%0d/%0d",n,cosine,sine,negative ? -x:x,negative ? -y:y);
            @(negedge clk);if(done) $fatal(1,"done not a pulse");
        end
        $display("PASS all 65536 CORDIC angles exactly match original 32-bit arithmetic; largest vector=%0d",largest);$finish;
    end
    initial begin #20000000;$fatal(1,"CORDIC watchdog");end
endmodule
