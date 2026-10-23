`timescale 1ns/1ps
`default_nettype none
module a741_top(
    input wire clk,stop_n,
    input wire camera_pclk,camera_vsync,camera_href,input wire [7:0] camera_data,
    output wire camera_reset_n,inout wire camera_sclk,camera_sdat,
    input wire rgmii_rx_clk,input wire [3:0] rgmii_rxd,input wire rgmii_rx_ctl,
    output wire rgmii_tx_clk,output wire [3:0] rgmii_txd,output wire rgmii_tx_ctl,
    output wire eth_rst_n,eth_mdc,inout wire eth_mdio,
    input wire left_enc_a,left_enc_b,right_enc_a,right_enc_b,
    output wire left_in1,left_in2,right_in1,right_in2,output wire [7:0] led,
    output wire tmds_clk_p,tmds_clk_n,output wire [2:0] tmds_data_p,tmds_data_n,
    output wire [13:0] O_ddr_addr,output wire [2:0] O_ddr_ba,
    output wire O_ddr_cs_n,O_ddr_ras_n,O_ddr_cas_n,O_ddr_we_n,O_ddr_clk,O_ddr_clk_n,
    output wire O_ddr_cke,O_ddr_odt,O_ddr_reset_n,output wire [1:0] O_ddr_dqm,
    inout wire [15:0] IO_ddr_dq,inout wire [1:0] IO_ddr_dqs,IO_ddr_dqs_n
`ifdef A741_MOTION_LIDAR
    ,input wire imu_int,imu_xda,imu_xcl,imu_ad0,lidar_rx,
    inout wire imu_sda,imu_scl,
    output wire lidar_control
`elsif A741_IMU_TEST
    ,input wire imu_int,imu_xda,imu_xcl,imu_ad0,
    inout wire imu_sda,imu_scl
`elsif A741_P4_VERIFIED
    ,input wire imu_int,lidar_rx,
    inout wire imu_sda,imu_scl,imu_xda,imu_xcl,imu_ad0,lidar_control,tof_sda,tof_scl,tof_xshut
`endif
);
    wire pll50,pll125,unused24,locked;
    Gowin_PLL clocks(.clkin(clk),.clkout0(pll50),.clkout1(pll125),.clkout2(unused24),
        .lock(locked),.mdclk(clk),.reset(!stop_n));
    wire global_n=stop_n && locked;
    wire control_n,net_n,rx_n,tx_n;
    reset_sync creset(.clk(clk),.async_n(global_n),.rst_n(control_n));
    reset_sync nreset(.clk(pll50),.async_n(global_n),.rst_n(net_n));
    reset_sync rxreset(.clk(rgmii_rx_clk),.async_n(global_n && eth_rst_n),.rst_n(rx_n));
    reset_sync txreset(.clk(pll125),.async_n(global_n),.rst_n(tx_n));
    wire camera_ready,camera_error,phy_ready;
    ov5640_board_init camera(.clk(clk),.rst_n(control_n),.camera_reset_n(camera_reset_n),
        .scl(camera_sclk),.sda(camera_sdat),.ready(camera_ready),.error(camera_error));
    // Preserve the PHY reset/autonegotiation sequence from the user-verified
    // A741 image.  PHY diagnostics must not hold the Ethernet MAC disabled.
    phy_reg_config phy(.Clk(clk),.Rst_n(control_n),.Phy_rst_n(eth_rst_n),
        .Rd_Data(),.Phy_init_done(phy_ready),.mdc(eth_mdc),.mdio(eth_mdio));
    (* ASYNC_REG="TRUE" *) reg [1:0] camera_ready_sync;
    always @(posedge camera_pclk or negedge global_n)
        if(!global_n) camera_ready_sync<=0;
        else camera_ready_sync<={camera_ready_sync[0],camera_ready};
    (* ASYNC_REG="TRUE" *) reg [1:0] phy_ready_rx,phy_ready_tx;
    always @(posedge rgmii_rx_clk or negedge rx_n)
        if(!rx_n) phy_ready_rx<=0;
        else phy_ready_rx<={phy_ready_rx[0],phy_ready};
    always @(posedge pll125 or negedge tx_n)
        if(!tx_n) phy_ready_tx<=0;
        else phy_ready_tx<={phy_ready_tx[0],phy_ready};
    wire [7:0] gmii_rxd,gmii_txd;
    wire gmii_dv,gmii_er,gmii_en,gmii_txer;
    acg720_rgmii_rx receiver(.rx_clk(rgmii_rx_clk),.rxd(rgmii_rxd),.rx_ctl(rgmii_rx_ctl),
        .gmii_data(gmii_rxd),.gmii_valid(gmii_dv),.gmii_error(gmii_er));
    gmii_to_rgmii transmitter(.reset_n(global_n),.gmii_tx_clk(pll125),.gmii_txd(gmii_txd),
        .gmii_txen(gmii_en),.gmii_txer(gmii_txer),.rgmii_tx_clk(rgmii_tx_clk),
        .rgmii_txd(rgmii_txd),.rgmii_txen(rgmii_tx_ctl));
    wire [7:0] rx_data,tx_data;
    wire rx_valid,rx_last,rx_bad,rx_ready,tx_valid,tx_last,tx_bad,tx_ready;
    wire rx_bad_fcs,rx_good_frame;
    wire [7:0] mac_diagnostic;
    a741_net_health net_health(.clk(clk),.rst_n(control_n),.rx_good_frame(rx_good_frame),
        .rx_bad_fcs(rx_bad_fcs),.status(mac_diagnostic));
    eth_mac_1g_fifo mac(.rx_clk(rgmii_rx_clk),.rx_rst(!rx_n),.tx_clk(pll125),.tx_rst(!tx_n),
        .logic_clk(clk),.logic_rst(!control_n),
        .tx_axis_tdata(tx_data),.tx_axis_tkeep(1'b1),.tx_axis_tvalid(tx_valid),.tx_axis_tready(tx_ready),
        .tx_axis_tlast(tx_last),.tx_axis_tuser(tx_bad),
        .rx_axis_tdata(rx_data),.rx_axis_tvalid(rx_valid),.rx_axis_tready(rx_ready),
        .rx_axis_tlast(rx_last),.rx_axis_tuser(rx_bad),
        .gmii_rxd(gmii_rxd),.gmii_rx_dv(gmii_dv),.gmii_rx_er(gmii_er),
        .gmii_txd(gmii_txd),.gmii_tx_en(gmii_en),.gmii_tx_er(gmii_txer),
        .rx_clk_enable(1'b1),.tx_clk_enable(1'b1),.rx_mii_select(1'b0),.tx_mii_select(1'b0),
        .cfg_ifg(8'd12),.cfg_tx_enable(phy_ready_tx[1]),.cfg_rx_enable(phy_ready_rx[1]),
        .rx_error_bad_fcs(rx_bad_fcs),.rx_fifo_good_frame(rx_good_frame));
    wire raw_l1,raw_l2,raw_r1,raw_r2;
`ifdef A741_MOTION_LIDAR
    localparam SENSOR_PINS_ENABLED=0,IMU_TEST=0,MOTION_LIDAR=1;
    wire tof_sda,tof_scl,tof_xshut;
`elsif A741_IMU_TEST
    localparam SENSOR_PINS_ENABLED=0,IMU_TEST=1,MOTION_LIDAR=0;
    wire lidar_rx=1'b1;
    wire tof_sda,tof_scl,tof_xshut;
`elsif A741_P4_VERIFIED
    localparam SENSOR_PINS_ENABLED=1,IMU_TEST=0,MOTION_LIDAR=0;
    assign imu_xda=1'bz;assign imu_xcl=1'bz;assign imu_ad0=1'bz;assign lidar_control=1'bz;
`else
    localparam SENSOR_PINS_ENABLED=0,IMU_TEST=0,MOTION_LIDAR=0;
    wire imu_int=1'b0,lidar_rx=1'b1;
    wire imu_sda,imu_scl,tof_sda,tof_scl,tof_xshut;
`endif
    wire serial_clk,pixel_clk,video_lock,video_n;
    A741_Video_PLL video_pll(.clkin(clk),.clkout0(),.clkout1(serial_clk),
        .lock(video_lock),.mdclk(clk),.reset(!stop_n));
    CLKDIV pixel_divider(.HCLKIN(serial_clk),.RESETN(video_lock),.CLKOUT(pixel_clk),.CALIB(1'b1));
    defparam pixel_divider.DIV_MODE="5";
    assign video_n=global_n && video_lock;
    wire memory_clk,ddr_lock,pll_stop,ui_clk,ui_rst,calibrated;
    wire [7:0] mdrp_data,mdrp_read;wire [1:0] mdrp_op;wire mdrp_inc;
    reg [15:0] ddr_lock_sync;reg pll_stop_d,mdrp_write;
    always @(posedge clk or negedge stop_n)
        if(!stop_n) begin ddr_lock_sync<=0;pll_stop_d<=0;mdrp_write<=0;end
        else begin
            ddr_lock_sync<={ddr_lock_sync[14:0],ddr_lock};
            pll_stop_d<=pll_stop;mdrp_write<=ddr_lock_sync[15] && (pll_stop_d!=pll_stop);
        end
    ddr_pll memory_pll(.clkin(clk),.clkout0(),.clkout1(),.clkout2(memory_clk),.lock(ddr_lock),
        .mdopc(mdrp_op),.mdainc(mdrp_inc),.mdwdi(mdrp_data),.mdrdo(mdrp_read),
        .pll_init_bypass(ddr_lock_sync[15]),.mdclk(clk),.reset(!stop_n));
    pll_mDRP_intf mdrp(.clk(clk),.rst_n(stop_n),.pll_lock(ddr_lock_sync[15]),.wr(mdrp_write),
        .mdrp_inc(mdrp_inc),.mdrp_op(mdrp_op),.mdrp_wdata(mdrp_data),.mdrp_rdata(mdrp_read));
    wire [27:0] app_addr;wire [2:0] app_cmd;wire app_en,app_rdy;
    wire [127:0] app_wdata,app_rdata;wire app_wen,app_wend,app_wrdy,app_rvalid;
    DDR3_Memory_Interface_Top memory(.clk(clk),.memory_clk(memory_clk),.pll_lock(ddr_lock),.rst_n(stop_n),
        .pll_stop(pll_stop),.cmd_ready(app_rdy),.cmd(app_cmd),.cmd_en(app_en),.addr(app_addr),
        .wr_data_rdy(app_wrdy),.wr_data(app_wdata),.wr_data_en(app_wen),.wr_data_end(app_wend),.wr_data_mask(16'd0),
        .rd_data(app_rdata),.rd_data_valid(app_rvalid),.rd_data_end(),
        .sr_req(1'b0),.ref_req(1'b0),.sr_ack(),.ref_ack(),.init_calib_complete(calibrated),
        .clk_out(ui_clk),.ddr_rst(ui_rst),.burst(1'b1),
        .O_ddr_addr(O_ddr_addr),.O_ddr_ba(O_ddr_ba),.O_ddr_cs_n(O_ddr_cs_n),
        .O_ddr_ras_n(O_ddr_ras_n),.O_ddr_cas_n(O_ddr_cas_n),.O_ddr_we_n(O_ddr_we_n),
        .O_ddr_clk(O_ddr_clk),.O_ddr_clk_n(O_ddr_clk_n),.O_ddr_cke(O_ddr_cke),.O_ddr_odt(O_ddr_odt),
        .O_ddr_reset_n(O_ddr_reset_n),.O_ddr_dqm(O_ddr_dqm),.IO_ddr_dq(IO_ddr_dq),
        .IO_ddr_dqs(IO_ddr_dqs),.IO_ddr_dqs_n(IO_ddr_dqs_n));
    wire ui_n;
    reset_sync ui_reset(.clk(ui_clk),.async_n(video_n && !ui_rst),.rst_n(ui_n));
    wire [15:0] rgb;wire de,hs,vs,frame_ready,camera_bad,ddr_bad,overflow;
    wire [7:0] vd;wire vv,vl,vr;wire [15:0] vlen;wire [31:0] frames;
    wire [895:0] snapshot;wire [255:0] fusion_snapshot;wire [7:0] state;wire [15:0] faults;
    a741_video video(.clk(clk),.rst_n(video_n),.cam_clk(camera_pclk),.cam_ready(camera_ready_sync[1]),
        .cam_vsync(camera_vsync),.cam_href(camera_href),.cam_data(camera_data),
        .ui_clk(ui_clk),.ui_rst_n(ui_n),.calibrated(calibrated),.pixel_clk(pixel_clk),
        .app_addr(app_addr),.app_cmd(app_cmd),.app_en(app_en),.app_rdy(app_rdy),
        .app_wdf_data(app_wdata),.app_wdf_wren(app_wen),.app_wdf_end(app_wend),.app_wdf_rdy(app_wrdy),
        .app_rd_data(app_rdata),.app_rd_valid(app_rvalid),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot),
        .rgb(rgb),.de(de),.hsync(hs),.vsync(vs),.video_data(vd),.video_valid(vv),.video_last(vl),.video_length(vlen),.video_ready(vr),
        .frame_available(frame_ready),.camera_error(camera_bad),.ddr_error(ddr_bad),.overflow(overflow),.frames(frames));
    a741_hdmi hdmi(.pixel_clk(pixel_clk),.serial_clk(serial_clk),.rst_n(video_n),.rgb(rgb),
        .hsync(hs),.vsync(vs),.de(de),.tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
    (* ASYNC_REG="TRUE" *) reg [1:0] ddr_ready_sync;
    always @(posedge clk or negedge control_n)
        if(!control_n) ddr_ready_sync<=0;else ddr_ready_sync<={ddr_ready_sync[0],calibrated};
    wire lidar_pwm;
`ifdef A741_MOTION_LIDAR
    assign lidar_control=global_n && lidar_pwm;
`endif
    a741_core #(.SENSOR_PINS_ENABLED(SENSOR_PINS_ENABLED),.IMU_TEST(IMU_TEST),.MOTION_LIDAR(MOTION_LIDAR)) core(.clk(clk),.rst_n(control_n),
        .mac_diagnostic(mac_diagnostic),.phy_ready(phy_ready),.phy_error(1'b0),
        .phy_diagnostic(128'd0),
        .lidar_control(lidar_pwm),
        .imu_int(imu_int),.imu_sda(imu_sda),.imu_scl(imu_scl),.lidar_rx(lidar_rx),
        .tof_sda(tof_sda),.tof_scl(tof_scl),.tof_xshut(tof_xshut),
        .left_a(left_enc_a),.left_b(left_enc_b),.right_a(right_enc_a),.right_b(right_enc_b),
        .left_in1(raw_l1),.left_in2(raw_l2),.right_in1(raw_r1),.right_in2(raw_r2),
        .eth_rx_data(rx_data),.eth_rx_valid(rx_valid),.eth_rx_last(rx_last),.eth_rx_bad(rx_bad),.eth_rx_ready(rx_ready),
        .eth_tx_data(tx_data),.eth_tx_valid(tx_valid),.eth_tx_last(tx_last),.eth_tx_bad(tx_bad),.eth_tx_ready(tx_ready),
        .video_data(vd),.video_valid(vv),.video_last(vl),.video_length(vlen),.video_ready(vr),
        .ddr_ready(ddr_ready_sync[1]),.frame_ready(frame_ready),.camera_error(camera_bad),
        .ddr_error(ddr_bad),.video_overflow(overflow),.video_frames(frames),.snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.state(state),.faults(faults));
    assign left_in1=IMU_TEST ? 1'b0:global_n && raw_l1;assign left_in2=IMU_TEST ? 1'b0:global_n && raw_l2;
    assign right_in1=IMU_TEST ? 1'b0:global_n && raw_r1;assign right_in2=IMU_TEST ? 1'b0:global_n && raw_r2;
    assign led={faults!=0,overflow,ddr_bad,frame_ready,ddr_ready_sync[1],phy_ready,camera_ready,locked};
endmodule
`default_nettype wire
