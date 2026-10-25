`timescale 1ns/1ps
module ray_mapper_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,cancel=0;
    wire busy,update_valid;wire [6:0] update_x,update_y;wire [1:0] update_value;wire done,invalid;
    a741_ray_mapper dut(.clk(clk),.rst_n(rst_n),.start(start),.cancel(cancel),.origin_x(7'd1),.origin_y(7'd1),
        .endpoint_x(7'd4),.endpoint_y(7'd2),.busy(busy),.update_valid(update_valid),
        .update_x(update_x),.update_y(update_y),.update_value(update_value),.done(done),.invalid(invalid));
    integer count=0;
    always @(negedge clk) if(update_valid) begin
        if(count==0 && {update_x,update_y,update_value}!=={7'd1,7'd1,2'b01}) $fatal(1,"ray origin");
        if(count==3 && {update_x,update_y,update_value}!=={7'd4,7'd2,2'b10}) $fatal(1,"ray endpoint");
        count=count+1;
    end
    initial begin
        #30;rst_n=1;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(done);@(negedge clk);#1;
        if(count!=4 || busy || invalid) $fatal(1,"ray length %0d",count);
        $display("PASS Bresenham ray marks free path and occupied endpoint");$finish;
    end
    initial begin #10000;$fatal(1,"watchdog");end
endmodule
