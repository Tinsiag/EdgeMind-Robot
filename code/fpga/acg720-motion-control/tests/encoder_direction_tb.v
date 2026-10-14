`timescale 1ns/1ps
module encoder_direction_tb;
    reg clk=0,rstn=0,la=0,lb=0,ra=0,rb=0;
    wire signed [1:0] ls,rs;
    wire li,ri;
    integer lc=0,rc=0;
    always #5 clk=~clk;
    // Instantiate the actual top-level to check its configured inversion.
    motion_top #(.CLK_HZ(5000000)) dut(.clk(clk),.stop_n(rstn),.uart_rx(1'b1),
        .left_enc_a(la),.left_enc_b(lb),.right_enc_a(ra),.right_enc_b(rb),
        .uart_tx(),.left_in1(),.left_in2(),.right_in1(),.right_in2(),.led());
    assign ls=dut.left_step; assign rs=dut.right_step;
    assign li=dut.left_invalid; assign ri=dut.right_invalid;
    always @(posedge clk) if(rstn) begin
        lc=lc+$signed(ls); rc=rc+$signed(rs);
        if(li||ri) $fatal(1,"Unexpected invalid AB transition");
    end
    task phase;
        input [1:0] l,r;
        begin @(negedge clk);{la,lb}=l;{ra,rb}=r;repeat(8) @(negedge clk);end
    endtask
    initial begin
        repeat(4) @(negedge clk);rstn=1;repeat(8) @(negedge clk);
        // Raw left forward: 00,01,11,10,00; right forward is reversed.
        phase(2'b01,2'b10);phase(2'b11,2'b11);phase(2'b10,2'b01);phase(0,0);
        if(lc!=4||rc!=4) $fatal(1,"Forward expected +4/+4 got %0d/%0d",lc,rc);
        phase(2'b10,2'b01);phase(2'b11,2'b11);phase(2'b01,2'b10);phase(0,0);
        if(lc!=0||rc!=0) $fatal(1,"Reverse expected return to 0/0 got %0d/%0d",lc,rc);
        $display("PASS top encoder direction: forward +4/+4, reverse -4/-4");$finish;
    end
    initial begin #10000;$fatal(1,"Direction watchdog");end
endmodule
