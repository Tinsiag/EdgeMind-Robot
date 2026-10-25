`timescale 1ns/1ps
// Validate the actual official test generator and byte combiner independently.
module ch38_test_source_tb;
    reg clk=0,reset=1;always #10 clk=~clk;
    wire [7:0] dat;wire valid;
    wire [15:0] pixel;wire pixel_valid;
    integer n=0,col,hi,lo;
    test_dat_gen #(.DISP_WIDTH(1600),.DISP_HEIGHT(2),.DATA_WIDTH(8),.DISP_MODE(0))
        gen(.clk(clk),.reset(reset),.gen_en(1'b1),.test_dat(dat),
        .test_dat_vaild(valid),.test_dat_hs(),.test_dat_vs(),.test_dat_col(),.test_dat_row());
    bit8_trans_bit16 conv(.clk(clk),.reset_p(reset),.bit8_in(dat),
        .bit8_in_valid(valid),.bit16_out(pixel),.bit16_out_valid(pixel_valid));
    always @(posedge clk)if(!reset && pixel_valid)begin
        col=n%800;hi=(2*col+1)%256;lo=(2*col+2)%256;
        if(pixel !== (hi*256+lo))$fatal(1,"Official source mismatch index=%0d got=%h",n,pixel);
        n=n+1;
        if(n==1600)begin $display("PASS: official byte source + converter, 2 full rows (1600 pixels)");$finish;end
    end
    initial begin repeat(5)@(negedge clk);reset=0;end
    initial begin #1000000;$fatal(1,"Official source watchdog");end
endmodule
// The unused ROM image output is not selected by DISP_MODE=0.
module rom_image(input clk,input [15:0]addr,output [15:0]dout);
    assign dout=0;
endmodule
