`timescale 1ns/1ps
module ray_mapper_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,cancel=0;
    reg [6:0] origin_x=1,origin_y=1,endpoint_x=4,endpoint_y=2;
    wire busy,update_valid;wire [6:0] update_x,update_y;wire [1:0] update_value;wire done,invalid;
    a741_ray_mapper dut(.clk(clk),.rst_n(rst_n),.start(start),.cancel(cancel),.origin_x(origin_x),.origin_y(origin_y),
        .endpoint_x(endpoint_x),.endpoint_y(endpoint_y),.busy(busy),.update_valid(update_valid),
        .update_x(update_x),.update_y(update_y),.update_value(update_value),.done(done),.invalid(invalid));
    integer count=0,last_x,last_y,current_x,current_y;reg first_ray=1;
    always @(negedge clk) if(update_valid) begin
        current_x=update_x;current_y=update_y;
        if(first_ray && count==0 && {update_x,update_y,update_value}!=={7'd1,7'd1,2'b01}) $fatal(1,"ray origin");
        if(first_ray && count==3 && {update_x,update_y,update_value}!=={7'd4,7'd2,2'b10}) $fatal(1,"ray endpoint");
        if(count==0 && {update_x,update_y}!={origin_x,origin_y}) $fatal(1,"ray start changed");
        if(count!=0 && (current_x>last_x+1 || current_x<last_x-1 || current_y>last_y+1 || current_y<last_y-1 ||
            (update_x==last_x && update_y==last_y))) $fatal(1,"nonadjacent/repeated ray cell");
        if(update_value!==((update_x==endpoint_x && update_y==endpoint_y) ? 2'b10:2'b01)) $fatal(1,"ray cell occupancy");
        last_x=update_x;last_y=update_y;
        count=count+1;
    end
    task ray(input [6:0] ox,oy,ex,ey);
        integer expected_length,deltax,deltay;
        begin
            @(negedge clk);origin_x=ox;origin_y=oy;endpoint_x=ex;endpoint_y=ey;count=0;start=1;
            @(negedge clk);start=0;
            wait(done);@(negedge clk);#1;
            deltax=ex>ox ? ex-ox:ox-ex;deltay=ey>oy ? ey-oy:oy-ey;
            expected_length=(deltax>deltay ? deltax:deltay)+1;
            if(count!=expected_length || busy || invalid || last_x!=ex || last_y!=ey) $fatal(1,"ray length/endpoint");
        end
    endtask
    initial begin
        #30;rst_n=1;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(done);@(negedge clk);#1;
        if(count!=4 || busy || invalid) $fatal(1,"ray length %0d",count);
        first_ray=0;
        ray(64,64,127,90);ray(64,64,90,127);ray(64,64,0,90);ray(64,64,30,127);
        ray(64,64,0,30);ray(64,64,30,0);ray(64,64,127,30);ray(64,64,90,0);
        ray(0,0,127,127);ray(127,127,0,0);ray(17,17,17,17);ray(0,0,0,127);ray(127,0,0,0);
        // Cancel the newly added initialization stage before any map update.
        @(negedge clk);start=1;@(negedge clk);start=0;cancel=1;
        @(negedge clk);cancel=0;repeat(3) @(negedge clk);
        if(busy || update_valid || done) $fatal(1,"canceled setup emitted ray data");
        ray(1,1,4,2);
        $display("PASS Bresenham octants, full-span/zero-length rays, free/occupied cells and setup cancellation");$finish;
    end
    initial begin #30000;$fatal(1,"watchdog");end
endmodule
