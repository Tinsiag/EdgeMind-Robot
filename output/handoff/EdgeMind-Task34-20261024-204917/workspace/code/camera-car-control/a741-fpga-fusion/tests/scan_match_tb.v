`timescale 1ns/1ps
module scan_match_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ms_tick=0,enable=1,cancel=0,point_valid=0,scan_end=0;
    reg signed [31:0] endpoint_x=1000,endpoint_y=1000,pose_x=0,pose_y=0;
    wire busy,map_read;wire [13:0] map_address;reg map_done=0;reg [1:0] map_value=2;
    wire result_valid,accepted,localized;wire signed [15:0] correction_x,correction_y,correction_yaw;wire [7:0] quality;
    reg known_map=1,ambiguous=0;
    a741_scan_match dut(.*);
    always @(posedge clk) begin
        map_done<=map_read;
        if(map_read) map_value<=!known_map ? 2'b00:ambiguous ? 2'b10:
            ((map_address[6:0]==44 || map_address[6:0]==84) && (map_address[13:7]==44 || map_address[13:7]==84)) ? 2'b10:2'b01;
    end
    task scan;
        integer n;
        begin
            for(n=0;n<144;n=n+1) begin @(negedge clk);point_valid=1;endpoint_x=(n/8)%2 ? 1025:-975;endpoint_y=(n/16)%2 ? 1025:-975;
                @(negedge clk);point_valid=0;end
            @(negedge clk);point_valid=1;scan_end=1;@(negedge clk);point_valid=0;scan_end=0;
            wait(result_valid);#1;@(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;scan();scan();
        if(!localized || !accepted || quality!=100) $fatal(1,"strong zero-offset match not accepted quality=%0d best=%0d second=%0d",quality,dut.best_score,dut.second_score);
        known_map=0;scan();scan();
        if(localized || accepted || quality!=0) $fatal(1,"unknown map retained localization");
        known_map=1;ambiguous=1;scan();scan();
        if(localized || accepted) $fatal(1,"ambiguous all-occupied map accepted localization");
        cancel=1;@(negedge clk);cancel=0;#1;if(busy || localized) $fatal(1,"cancel did not invalidate matcher");
        $display("PASS bounded correlative matching, repeated confidence gate, unknown rejection and cancel");$finish;
    end
    initial begin #3000000;$fatal(1,"watchdog");end
endmodule
