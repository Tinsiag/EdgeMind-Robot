`timescale 1ns/1ps
`default_nettype none
// Weighted 8-neighbour A*, bounded to the complete 128x128 map.
// All large tables have synchronous read ports for block-RAM inference.
module a741_path_planner(
    input wire clk,rst_n,start,cancel,map_valid,
    input wire [6:0] start_x,start_y,goal_x,goal_y,
    output reg map_read_valid,output reg [13:0] map_read_address,
    input wire [1:0] map_read_value,input wire map_read_done,
    output reg busy,path_valid,no_path,path_cell_valid,
    output reg [6:0] path_cell_x,path_cell_y,output reg path_cell_last,
    output reg [13:0] expanded_nodes
);
    localparam IDLE=0,INIT=1,READ_REQ=2,READ_WAIT=3,START_CHECK=4,GOAL_CHECK=5,
        SCAN_BEGIN=6,SCAN_REQ=7,SCAN_EVAL=8,SELECT=9,NEIGHBOR=10,
        COORD_CHECK=11,SIDE1_CHECK=12,SIDE2_CHECK=13,TARGET_CHECK=14,
        PATH_REQ=15,PATH_EMIT=16,FAILED=17,SCAN_COST=18,TARGET_EVAL=19,TARGET_WRITE=20;
    reg [4:0] state,after_read;
    // [19:18]: 00 unseen, 01 open, 10 closed; [17:0]: accumulated path cost.
    reg [19:0] records[0:16383];reg [3:0] parents[0:16383];
    reg [19:0] record_q;reg [3:0] parent_q;
    reg [13:0] init_index,scan_index,current_node,best_node,start_node,goal_node,neighbor_node,request_address;
    reg [3:0] neighbor_index;
    reg signed [8:0] neighbor_x,neighbor_y;
    reg [17:0] current_g,best_f,best_g;
    reg [6:0] gx,gy;
    reg signed [1:0] step_x,step_y;
    reg best_found;
    reg [17:0] heuristic_q,score_q,scan_g;
    reg scan_open;
    reg update_neighbor;reg [17:0] candidate_q;
    reg [14:0] route_steps,expanded;
    reg [15:0] wait_age;
    wire diagonal=step_x!=0 && step_y!=0;
    wire [17:0] candidate_g=current_g+(diagonal ? 18'd14:18'd10);
    wire [1:0] back_x=-step_x,back_y=-step_y;
    wire signed [8:0] parent_x=$signed({1'b0,current_node[6:0]})+$signed(parent_q[1:0]);
    wire signed [8:0] parent_y=$signed({1'b0,current_node[13:7]})+$signed(parent_q[3:2]);
    wire [13:0] ram_address=(state==SCAN_REQ || state==SCAN_EVAL) ? scan_index:neighbor_node;
    function signed [1:0] delta_x(input [2:0] n);
        begin case(n) 0:delta_x=-1;1:delta_x=0;2:delta_x=1;3:delta_x=-1;
            4:delta_x=1;5:delta_x=-1;6:delta_x=0;default:delta_x=1;endcase end
    endfunction
    function signed [1:0] delta_y(input [2:0] n);
        begin case(n) 0:delta_y=-1;1:delta_y=-1;2:delta_y=-1;3:delta_y=0;
            4:delta_y=0;5:delta_y=1;6:delta_y=1;default:delta_y=1;endcase end
    endfunction
    function [17:0] estimate(input [13:0] node,input [6:0] target_x,target_y);
        reg [7:0] ax,ay,lo,hi;
        begin
            ax=node[6:0]>=target_x ? node[6:0]-target_x:target_x-node[6:0];
            ay=node[13:7]>=target_y ? node[13:7]-target_y:target_y-node[13:7];
            lo=ax<ay ? ax:ay;hi=ax>ay ? ax:ay;estimate=lo*14+(hi-lo)*10;
        end
    endfunction
    // A single write port and registered read on each table, no asynchronous reset.
    always @(posedge clk) begin
        record_q<=records[ram_address];parent_q<=parents[current_node];
        if(rst_n && !cancel) begin
            if(state==INIT) begin records[init_index]<={2'b00,18'h3ffff};parents[init_index]<=0;end
            else if(state==READ_WAIT && map_read_done && after_read==GOAL_CHECK && map_read_value==2'b01) begin
                records[start_node]<={2'b01,18'd0};parents[start_node]<=0;
            end else if(state==SELECT && best_found && expanded<16384) records[best_node]<={2'b10,best_g};
            else if(state==TARGET_WRITE && update_neighbor) begin
                records[neighbor_node]<={2'b01,candidate_q};parents[neighbor_node]<={back_y,back_x};
            end
        end
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            state<=IDLE;after_read<=START_CHECK;init_index<=0;scan_index<=0;current_node<=0;best_node<=0;
            start_node<=0;goal_node<=0;neighbor_node<=0;neighbor_index<=0;neighbor_x<=0;neighbor_y<=0;request_address<=0;
            map_read_valid<=0;map_read_address<=0;current_g<=0;best_f<=0;best_g<=0;best_found<=0;
            busy<=0;path_valid<=0;no_path<=0;path_cell_valid<=0;path_cell_x<=0;path_cell_y<=0;path_cell_last<=0;
            expanded_nodes<=0;expanded<=0;gx<=0;gy<=0;step_x<=0;step_y<=0;route_steps<=0;wait_age<=0;
            heuristic_q<=0;score_q<=0;scan_g<=0;scan_open<=0;update_neighbor<=0;candidate_q<=0;
        end else begin
            map_read_valid<=0;path_cell_valid<=0;path_cell_last<=0;
            if(cancel || (busy && !map_valid)) begin state<=IDLE;busy<=0;path_valid<=0;no_path<=!cancel;end
            else case(state)
                IDLE:if(start) begin
                    busy<=map_valid;path_valid<=0;no_path<=!map_valid;expanded<=0;expanded_nodes<=0;route_steps<=0;
                    gx<=goal_x;gy<=goal_y;start_node<={start_y,start_x};goal_node<={goal_y,goal_x};
                    if(map_valid) begin init_index<=0;state<=INIT;end
                end
                INIT:if(init_index==16383) begin request_address<=start_node;after_read<=START_CHECK;state<=READ_REQ;end
                    else init_index<=init_index+1'b1;
                READ_REQ:begin map_read_address<=request_address;map_read_valid<=1;wait_age<=0;state<=READ_WAIT;end
                READ_WAIT:begin
                    wait_age<=wait_age+1'b1;
                    if(wait_age==65535) state<=FAILED;
                    else if(map_read_done) case(after_read)
                        START_CHECK:if(map_read_value==2'b01) begin request_address<=goal_node;after_read<=GOAL_CHECK;state<=READ_REQ;end else state<=FAILED;
                        GOAL_CHECK:if(map_read_value==2'b01) state<=SCAN_BEGIN;else state<=FAILED;
                        SIDE1_CHECK:if(map_read_value==2'b01) begin
                            request_address<={current_node[13:7],neighbor_x[6:0]};after_read<=SIDE2_CHECK;state<=READ_REQ;
                        end else begin neighbor_index<=neighbor_index+1'b1;state<=NEIGHBOR;end
                        SIDE2_CHECK:if(map_read_value==2'b01) begin request_address<=neighbor_node;after_read<=TARGET_CHECK;state<=READ_REQ;end
                            else begin neighbor_index<=neighbor_index+1'b1;state<=NEIGHBOR;end
                        TARGET_CHECK:if(map_read_value==2'b01) state<=TARGET_EVAL;
                            else begin neighbor_index<=neighbor_index+1'b1;state<=NEIGHBOR;end
                        default:state<=FAILED;
                    endcase
                end
                // Break block-RAM output -> cost compare -> block-RAM write
                // enable across cycles. Coordinates stay fixed until commit.
                TARGET_EVAL:begin
                    update_neighbor<=record_q[19:18]!=2'b10 && candidate_g<record_q[17:0];
                    candidate_q<=candidate_g;state<=TARGET_WRITE;
                end
                TARGET_WRITE:begin neighbor_index<=neighbor_index+1'b1;state<=NEIGHBOR;end
                SCAN_BEGIN:begin scan_index<=0;best_f<=18'h3ffff;best_g<=18'h3ffff;best_found<=0;state<=SCAN_REQ;end
                SCAN_REQ:begin heuristic_q<=estimate(scan_index,gx,gy);state<=SCAN_COST;end
                SCAN_COST:begin score_q<=record_q[17:0]+heuristic_q;scan_g<=record_q[17:0];scan_open<=record_q[19:18]==2'b01;state<=SCAN_EVAL;end
                SCAN_EVAL:begin
                    if(scan_open && (!best_found || score_q<best_f || (score_q==best_f && scan_g<best_g))) begin
                        best_f<=score_q;best_g<=scan_g;best_node<=scan_index;best_found<=1;
                    end
                    if(scan_index==16383) state<=SELECT;else begin scan_index<=scan_index+1'b1;state<=SCAN_REQ;end
                end
                SELECT:if(!best_found || expanded>=16384) state<=FAILED;
                    else begin
                        current_node<=best_node;current_g<=best_g;expanded<=expanded+1'b1;
                        if(expanded_nodes!=16383) expanded_nodes<=expanded_nodes+1'b1;
                        if(best_node==goal_node) begin route_steps<=0;state<=PATH_REQ;end
                        else begin neighbor_index<=0;state<=NEIGHBOR;end
                    end
                NEIGHBOR:if(neighbor_index==8) state<=SCAN_BEGIN;
                    else begin
                        step_x<=delta_x(neighbor_index[2:0]);step_y<=delta_y(neighbor_index[2:0]);
                        neighbor_x<=$signed({1'b0,current_node[6:0]})+delta_x(neighbor_index[2:0]);
                        neighbor_y<=$signed({1'b0,current_node[13:7]})+delta_y(neighbor_index[2:0]);state<=COORD_CHECK;
                    end
                COORD_CHECK:if(neighbor_x<0 || neighbor_x>127 || neighbor_y<0 || neighbor_y>127) begin neighbor_index<=neighbor_index+1'b1;state<=NEIGHBOR;end
                    else begin
                        neighbor_node<={neighbor_y[6:0],neighbor_x[6:0]};
                        request_address<=diagonal ? {neighbor_y[6:0],current_node[6:0]}:{neighbor_y[6:0],neighbor_x[6:0]};
                        after_read<=diagonal ? SIDE1_CHECK:TARGET_CHECK;state<=READ_REQ;
                    end
                PATH_REQ:state<=PATH_EMIT;
                PATH_EMIT:begin
                    path_cell_valid<=1;path_cell_x<=current_node[6:0];path_cell_y<=current_node[13:7];
                    if(current_node==start_node) begin path_cell_last<=1;path_valid<=1;busy<=0;state<=IDLE;end
                    else if(route_steps>=16383 || parent_q==0 || parent_x<0 || parent_x>127 || parent_y<0 || parent_y>127) state<=FAILED;
                    else begin current_node<={parent_y[6:0],parent_x[6:0]};route_steps<=route_steps+1'b1;state<=PATH_REQ;end
                end
                FAILED:begin no_path<=1;path_valid<=0;busy<=0;state<=IDLE;end
                default:state<=IDLE;
            endcase
        end
endmodule
`default_nettype wire
