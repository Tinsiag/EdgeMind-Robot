`timescale 1ns/1ps
`default_nettype none
// Keep the manufacturer's TMDS encoder, replace its fabric modulo-5 shift
// crossing with dedicated GW5A 10:1 serializers clocked by PCLK/FCLK.
module a741_hdmi(
    input wire pixel_clk,serial_clk,reset_clk,rst_n,input wire [15:0] rgb,input wire de,hsync,vsync,
    output wire tmds_clk_p,tmds_clk_n,output wire [2:0] tmds_data_p,tmds_data_n
);
    wire pixel_n;
    reset_sync pixel_reset(.clk(pixel_clk),.async_n(rst_n),.rst_n(pixel_n));
    wire [9:0] channels[0:3];
    a741_tmds_encode blue(.clk(pixel_clk),.rst_n(pixel_n),.din({rgb[4:0],3'd0}),
        .c0(hsync),.c1(vsync),.de(de),.dout(channels[0]));
    a741_tmds_encode green(.clk(pixel_clk),.rst_n(pixel_n),.din({rgb[10:5],2'd0}),
        .c0(1'b0),.c1(1'b0),.de(de),.dout(channels[1]));
    a741_tmds_encode red(.clk(pixel_clk),.rst_n(pixel_n),.din({rgb[15:11],3'd0}),
        .c0(1'b0),.c1(1'b0),.de(de),.dout(channels[2]));
    assign channels[3]=10'b1111100000;
    wire [3:0] p,n;
    genvar i;
    generate for(i=0;i<4;i=i+1) begin: lanes
        wire serial_data;
        // Divide-by-3 reset clock and divide-by-5 pixel clock cover every
        // integer serial-clock phase at startup. Keep reset FFs local to each
        // serializer so recovery/removal timing includes short physical paths.
        (* ASYNC_REG="TRUE", syn_preserve=1, syn_keep=1 *) reg [2:0] serial_reset_pipe;
        always @(posedge reset_clk or negedge rst_n)
            if(!rst_n) serial_reset_pipe<=3'b111;
            else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};
        OSER10 serializer(.PCLK(pixel_clk),.FCLK(serial_clk),.RESET(serial_reset_pipe[2]),.Q(serial_data),
            .D0(channels[i][0]),.D1(channels[i][1]),.D2(channels[i][2]),.D3(channels[i][3]),.D4(channels[i][4]),
            .D5(channels[i][5]),.D6(channels[i][6]),.D7(channels[i][7]),.D8(channels[i][8]),.D9(channels[i][9]));
        ELVDS_OBUF output_buffer(.I(serial_data),.O(p[i]),.OB(n[i]));
    end endgenerate
    assign {tmds_clk_p,tmds_data_p}=p;
    assign {tmds_clk_n,tmds_data_n}=n;
endmodule
`default_nettype wire
