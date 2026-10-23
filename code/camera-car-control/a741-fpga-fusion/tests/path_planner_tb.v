`timescale 1ns/1ps
module path_planner_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,cancel=0,map_valid=1;
    reg [6:0] start_x=64,start_y=64,goal_x=65,goal_y=65;
    wire map_read_valid;wire [13:0] map_read_address;reg [1:0] map_read_value=1;reg map_read_done=0;
    wire busy,path_valid,no_path,path_cell_valid,path_cell_last;wire [6:0] path_cell_x,path_cell_y;wire [13:0] expanded_nodes;
    reg block_goal=0,corner_block=0;integer count=0;
    integer previous_x,previous_y;
    a741_path_planner dut(.clk(clk),.rst_n(rst_n),.start(start),.cancel(cancel),.map_valid(map_valid),
        .start_x(start_x),.start_y(start_y),.goal_x(goal_x),.goal_y(goal_y),
        .map_read_valid(map_read_valid),.map_read_address(map_read_address),.map_read_value(map_read_value),.map_read_done(map_read_done),
        .busy(busy),.path_valid(path_valid),.no_path(no_path),.path_cell_valid(path_cell_valid),
        .path_cell_x(path_cell_x),.path_cell_y(path_cell_y),.path_cell_last(path_cell_last),.expanded_nodes(expanded_nodes));
    always @(posedge clk) begin
        map_read_done<=map_read_valid;
        if(map_read_valid) map_read_value<=block_goal && map_read_address=={goal_y,goal_x} ? 2'b10:
            corner_block && map_read_address!={start_y,start_x} && map_read_address!={goal_y,goal_x} ? 2'b10:2'b01;
    end
    always @(negedge clk) if(path_cell_valid && !block_goal && !corner_block) begin
        if(count==0 && {path_cell_x,path_cell_y}!=={goal_x,goal_y}) $fatal(1,"path must stream goal first");
        if(path_cell_last && {path_cell_x,path_cell_y}!=={start_x,start_y}) $fatal(1,"path must end at start");
        if(count>0 && (path_cell_x>previous_x+1 || path_cell_x+1<previous_x || path_cell_y>previous_y+1 || path_cell_y+1<previous_y))
            $fatal(1,"compressed parent edge is not adjacent");
        previous_x=path_cell_x;previous_y=path_cell_y;
        count=count+1;
    end
    initial begin
        #30;rst_n=1;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(path_valid);@(negedge clk);#1;
        if(count!=2 || no_path || busy || !path_cell_last) $fatal(1,"diagonal free path result count=%0d",count);
        block_goal=1;count=0;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(no_path);@(negedge clk);#1;
        if(path_valid || busy) $fatal(1,"occupied goal accepted");
        block_goal=0;corner_block=1;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(no_path);@(negedge clk);#1;
        if(path_valid || busy) $fatal(1,"diagonal corner-cutting accepted");
        corner_block=0;goal_x=70;goal_y=69;count=0;@(negedge clk);start=1;@(negedge clk);start=0;
        wait(path_valid);@(negedge clk);#1;
        if(count!=7 || dut.records[{goal_y,goal_x}][17:0]!=80) $fatal(1,"multi-edge path cost/length count=%0d",count);
        $display("PASS weighted A* known-free path, blocked goal and diagonal corner-cutting rejection");$finish;
    end
    initial begin #12000000;$fatal(1,"watchdog");end
endmodule
