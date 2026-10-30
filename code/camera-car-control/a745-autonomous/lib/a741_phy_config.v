`timescale 1ns/1ps
`default_nettype none
// RTL8211F-CG at PHY address 5. Datasheet section 7.17 requires at least
// 10 ms reset and 50 ms settling after release before register access.
// Keep 2 kHz MDC; enable and read back both RGMII delays.
// RX timing then follows RTL8211F Table 58's integrated-delay output window.
module a741_phy_config #(
    parameter CLOCK_HZ=50000000, MDC_HZ=2000,
    RESET_CYCLES=CLOCK_HZ/100, WAIT_CYCLES=CLOCK_HZ/20
)(input wire clk,rst_n, output reg phy_rst_n,ready,error,
  output wire mdc,inout wire mdio);
    reg [24:0] wait_count;
    reg [3:0] step;
    reg start,waiting;
    reg [15:0] saved_tx,saved_rx;
    reg read_op;
    reg [4:0] reg_addr;
    reg [15:0] tx_data;
    wire busy,done,ack_error;
    wire [15:0] rx_data;
    a741_mdio #(.CLOCK_HZ(CLOCK_HZ),.MDC_HZ(MDC_HZ)) bus(
        .clk(clk),.rst_n(rst_n && phy_rst_n),.start(start),.read_op(read_op),
        .phy_addr(5'd5),.reg_addr(reg_addr),.tx_data(tx_data),.rx_data(rx_data),
        .busy(busy),.done(done),.ack_error(ack_error),.mdc(mdc),.mdio(mdio));
    always @* begin
        read_op=0;reg_addr=0;tx_data=0;
        case(step)
            0: begin read_op=1;reg_addr=2;end
            1: begin read_op=1;reg_addr=3;end
            2: begin reg_addr=31;tx_data=16'h0d08;end
            3: begin read_op=1;reg_addr=17;end
            4: begin reg_addr=17;tx_data=saved_tx|16'h0100;end
            5: begin read_op=1;reg_addr=17;end
            6: begin read_op=1;reg_addr=21;end
            7: begin reg_addr=21;tx_data=saved_rx|16'h0008;end
            8: begin read_op=1;reg_addr=21;end
            9: begin reg_addr=31;tx_data=0;end
            10: begin reg_addr=0;tx_data=16'h1200;end
            11: begin read_op=1;reg_addr=0;end
            default: begin end
        endcase
    end
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            wait_count<=0;step<=0;start<=0;waiting<=0;
            phy_rst_n<=0;ready<=0;error<=0;saved_tx<=0;saved_rx<=0;
        end else begin
            start<=0;
            if(wait_count<RESET_CYCLES+WAIT_CYCLES) begin
                wait_count<=wait_count+1'b1;
                // One extra edge guarantees a full RESET_CYCLES interval
                // even when the controller reset is released between clocks.
                if(wait_count==RESET_CYCLES) phy_rst_n<=1;
            end else if(!ready && !error) begin
                if(!waiting && !busy) begin start<=1;waiting<=1;end
                else if(waiting && done) begin
                    waiting<=0;
                    if(ack_error || (step==0 && rx_data!=16'h001c) ||
                       (step==1 && (rx_data&16'hfff0)!=16'hc910) ||
                       (step==5 && rx_data!=(saved_tx|16'h0100)) ||
                       (step==8 && rx_data!=(saved_rx|16'h0008)) ||
                       (step==11 && !rx_data[12])) error<=1;
                    else begin
                        if(step==3) saved_tx<=rx_data;
                        if(step==6) saved_rx<=rx_data;
                        if(step==11) ready<=1;
                        else step<=step+1'b1;
                    end
                end
            end
        end
endmodule

// Clause 22 master. Read turnaround is checked; a missing PHY cannot publish
// ready. Open-drain MDIO passes two synchronizer registers and is sampled
// at each rising MDC edge. A completed transfer always releases the bus.
module a741_mdio #(parameter CLOCK_HZ=50000000,MDC_HZ=2000)(
    input wire clk,rst_n,start,read_op,input wire [4:0] phy_addr,reg_addr,
    input wire [15:0] tx_data,output reg [15:0] rx_data,
    output reg busy,done,ack_error,mdc,inout wire mdio
);
    localparam HALF_CYCLES=CLOCK_HZ/(2*MDC_HZ);
    localparam DIV_BITS=$clog2(HALF_CYCLES+1);
    reg [DIV_BITS-1:0] divider;
    reg [5:0] bit_index;
    reg [63:0] frame;
    reg reading,drive_low;
    (* ASYNC_REG="TRUE" *) reg [1:0] mdio_sync;
    assign mdio=drive_low ? 1'b0:1'bz;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) mdio_sync<=2'b11;
        else mdio_sync<={mdio_sync[0],mdio};
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            divider<=0;bit_index<=0;frame<=0;reading<=0;drive_low<=0;
            rx_data<=0;busy<=0;done<=0;ack_error<=0;mdc<=0;
        end else begin
            done<=0;
            if(!busy) begin
                mdc<=0;drive_low<=0;
                if(start) begin
                    frame<={32'hffffffff,2'b01,read_op ? 2'b10:2'b01,phy_addr,reg_addr,2'b10,tx_data};
                    reading<=read_op;bit_index<=0;divider<=0;rx_data<=0;
                    busy<=1;ack_error<=0;
                end
            end else if(divider==HALF_CYCLES-1) begin
                divider<=0;mdc<=!mdc;
                if(!mdc) begin
                    if(reading && bit_index==47 && mdio_sync[1]!=0) ack_error<=1;
                    if(reading && bit_index>=48) rx_data<={rx_data[14:0],mdio_sync[1]};
                end else if(bit_index==63) begin
                    busy<=0;done<=1;drive_low<=0;
                end else begin
                    bit_index<=bit_index+1'b1;
                    drive_low<=!(reading && bit_index>=45) && !frame[62-bit_index];
                end
            end else divider<=divider+1'b1;
        end
endmodule
`default_nettype wire
