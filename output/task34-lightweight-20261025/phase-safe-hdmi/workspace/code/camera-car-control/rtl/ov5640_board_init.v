`timescale 1ns/1ps
`default_nettype none
module ov5640_board_init #(parameter CLK_HZ=50000000,WIDTH=800,HEIGHT=480)(
    input wire clk,rst_n,
    output wire camera_reset_n,
    inout wire scl,sda,
    output reg ready,error
);
    reg [20:0] boot_count;
    wire sensor_released=boot_count>=CLK_HZ/1000;
    wire enable=boot_count>=CLK_HZ/1000*21;
    assign camera_reset_n=rst_n && sensor_released;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) boot_count<=0;
        else if(!enable) boot_count<=boot_count+1'b1;
    wire init_done,init_error;
    ov5640_ctrl #(.CLK_HZ(CLK_HZ),.SCCB_HZ(100000),.IMAGE_WIDTH(WIDTH),
        .IMAGE_HEIGHT(HEIGHT),.TABLE_LAST(254)) init(
        .clk(clk),.rst_n(rst_n),.enable(enable),.sccb_sda(sda),.sccb_scl(scl),
        .init_busy(),.init_done(init_done),.init_error(init_error),.last_read_id(),.table_index());
    reg [1:0] state;
    reg [3:0] index;
    reg start;
    wire done,ack_error,timeout;
    wire [7:0] value;
    reg [15:0] address;
    reg [7:0] expected;
    always @* begin
        address=16'h3808;expected=WIDTH>>8;
        case(index)
            1:begin address=16'h3809;expected=WIDTH & 255;end
            2:begin address=16'h380a;expected=HEIGHT>>8;end
            3:begin address=16'h380b;expected=HEIGHT & 255;end
            4:begin address=16'h4300;expected=8'h61;end
            5:begin address=16'h501f;expected=8'h01;end
            6:begin address=16'h5001;expected=8'ha3;end
            7:begin address=16'h503d;expected=8'h00;end
            8:begin address=16'h4741;expected=8'h00;end
            default:begin end
        endcase
    end
    sccb_master #(.CLK_HZ(CLK_HZ),.SCCB_HZ(100000)) verify(
        .clk(clk),.rst_n(rst_n),.start(start),.read(1'b1),.dev_addr(8'h78),
        .reg_addr(address),.wr_data(8'd0),.rd_data(value),.busy(),.done(done),
        .ack_error(ack_error),.timeout(timeout),.sccb_sda(sda),.sccb_scl(scl));
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin state<=0;index<=0;start<=0;ready<=0;error<=0;end
        else begin
            start<=0;
            if(init_error) begin error<=1;ready<=0;state<=3;end
            else case(state)
                0:if(init_done) begin start<=1;state<=1;end
                1:if(done) begin
                    if(ack_error || timeout || value!=expected) begin error<=1;state<=3;end
                    else if(index==8) begin ready<=1;state<=3;end
                    else begin index<=index+1'b1;state<=2;end
                end
                2:begin start<=1;state<=1;end
                default:begin end
            endcase
        end
endmodule
`default_nettype wire
