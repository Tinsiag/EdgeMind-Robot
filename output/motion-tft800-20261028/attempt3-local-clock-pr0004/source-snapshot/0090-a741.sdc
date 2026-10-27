create_clock -name sys_clk -period 20.000 [get_ports {clk}]
create_clock -name camera_pclk -period 10.000 [get_ports {camera_pclk}]
create_clock -name rgmii_rx_clk -period 8.000 [get_ports {rgmii_rx_clk}]
# Gowin derives PLL output clocks from the PLL primitive automatically.
# External timing numbers are conservative initial budgets, not board measurements.
set_input_delay -clock camera_pclk -max 4.000 [get_ports {camera_data[*] camera_vsync camera_href}]
set_input_delay -clock camera_pclk -min 0.000 [get_ports {camera_data[*] camera_vsync camera_href}]
# Reset and encoder inputs are asynchronous; encoders enter synchronizers.
set_false_path -from [get_ports {stop_n left_enc_a left_enc_b right_enc_a right_enc_b}]
# Keep CDC paths visible in this initial build for explicit report review.
create_generated_clock -name tx250m -source [get_ports {clk}] -multiply_by 5 [get_pins {clocks/u_pll/PLLA_inst/CLKOUT1}]
create_generated_clock -name tx125m -source [get_pins {clocks/u_pll/PLLA_inst/CLKOUT1}] -master_clock tx250m -divide_by 2 [get_pins {tx_divider/CLKOUT}]
create_generated_clock -name display33m -source [get_ports {clk}] -multiply_by 33 -divide_by 50 [get_pins {display_clocks/u_pll/PLLA_inst/CLKOUT0}]

create_generated_clock -name memory400m -source [get_ports {clk}] -multiply_by 8 -phase 0 -duty_cycle 50 [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}]
create_generated_clock -name ddr_ui100m -source [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}] -master_clock memory400m -divide_by 4 [get_pins {memory/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]
# Only implemented synchronizer inputs are excepted. Never cut whole clock groups.
# Gray pointers are registered; 10 ns bounds skew to the fastest source period.
set_max_delay -to [get_pins {video/*fifo/rg1_*/D video/*fifo/wg1_*/D}] 10
set_false_path -hold -to [get_pins {video/*fifo/rg1_*/D video/*fifo/wg1_*/D}]
# Mailbox request/ack toggles pass two flip-flops before use.
set_max_delay -to [get_pins {video/*/req_sync_0_s0/D video/*/ack_sync_0_s0/D}] 10
set_false_path -hold -to [get_pins {video/*/req_sync_0_s0/D video/*/ack_sync_0_s0/D}]
# Single bit diagnostics cross only through explicit two-stage synchronizers.
set_max_delay -to [get_pins {video/av_sync_0_s0/D video/er_sync_0_s0/D video/ce_sync_0_s0/D video/co_sync_0_s0/D ddr_ready_sync_0_s0/D camera_ready_sync_0_s0/D phy_ready_rx_0_s0/D phy_ready_tx_0_s0/D}] 10
set_false_path -hold -to [get_pins {video/av_sync_0_s0/D video/er_sync_0_s0/D video/ce_sync_0_s0/D video/co_sync_0_s0/D ddr_ready_sync_0_s0/D camera_ready_sync_0_s0/D phy_ready_rx_0_s0/D phy_ready_tx_0_s0/D}]
# Async assertion is intentional in reset synchronizer cells. All consumers
# must use the reset synchronized to their own clock (reviewed separately).
set_false_path -to [get_pins {*reset*/pipe*/CLEAR}]
# verilog-ethernet axis_async_fifo: registered Gray pointers and request/ack
# toggles enter explicit destination synchronizers (source lines 568-603).
# Status sync1 is a source toggle; sync2 is its first destination stage (607-640).
# Use the fastest participating period, 8ns, and cut hold only at those inputs.
set_max_delay 8 -to [get_pins {mac/tx_fifo/fifo_inst/rd_ptr_gray_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_gray_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_update_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_update_ack_sync1_reg*/D mac/tx_fifo/fifo_inst/overflow_sync2_reg*/D mac/tx_fifo/fifo_inst/bad_frame_sync2_reg*/D mac/tx_fifo/fifo_inst/good_frame_sync2_reg*/D}]
set_false_path -hold -to [get_pins {mac/tx_fifo/fifo_inst/rd_ptr_gray_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_gray_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_update_sync1_reg*/D mac/tx_fifo/fifo_inst/wr_ptr_update_ack_sync1_reg*/D mac/tx_fifo/fifo_inst/overflow_sync2_reg*/D mac/tx_fifo/fifo_inst/bad_frame_sync2_reg*/D mac/tx_fifo/fifo_inst/good_frame_sync2_reg*/D}]
set_max_delay 8 -to [get_pins {mac/rx_fifo/fifo_inst/rd_ptr_gray_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_gray_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_update_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_update_ack_sync1_reg*/D mac/rx_fifo/fifo_inst/overflow_sync2_reg*/D mac/rx_fifo/fifo_inst/bad_frame_sync2_reg*/D mac/rx_fifo/fifo_inst/good_frame_sync2_reg*/D}]
set_false_path -hold -to [get_pins {mac/rx_fifo/fifo_inst/rd_ptr_gray_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_gray_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_update_sync1_reg*/D mac/rx_fifo/fifo_inst/wr_ptr_update_ack_sync1_reg*/D mac/rx_fifo/fifo_inst/overflow_sync2_reg*/D mac/rx_fifo/fifo_inst/bad_frame_sync2_reg*/D mac/rx_fifo/fifo_inst/good_frame_sync2_reg*/D}]
# FRAME_FIFO holds the binary committed pointer from the request until the
# acknowledgement; capture follows two destination request sync stages.
# Only that held bus is bounded; subsequent synchronous pointer logic is timed.
set_max_delay 8 -from [get_pins {mac/tx_fifo/fifo_inst/wr_ptr_sync_commit_reg*/Q}] -to [get_pins {mac/tx_fifo/fifo_inst/wr_ptr_commit_sync_reg*/D}]
set_false_path -hold -from [get_pins {mac/tx_fifo/fifo_inst/wr_ptr_sync_commit_reg*/Q}] -to [get_pins {mac/tx_fifo/fifo_inst/wr_ptr_commit_sync_reg*/D}]
set_max_delay 8 -from [get_pins {mac/rx_fifo/fifo_inst/wr_ptr_sync_commit_reg*/Q}] -to [get_pins {mac/rx_fifo/fifo_inst/wr_ptr_commit_sync_reg*/D}]
set_false_path -hold -from [get_pins {mac/rx_fifo/fifo_inst/wr_ptr_sync_commit_reg*/Q}] -to [get_pins {mac/rx_fifo/fifo_inst/wr_ptr_commit_sync_reg*/D}]
# axis_async_fifo.v:355-380: sync1 is in the opposite source domain;
# sync2 is the first destination stage and sync3 is the second. Bound only
# those four CDC links; all sync2 -> sync3 and reset-consumer paths stay timed.
# Source reset registers can be shared by synthesis across the two FIFOs.
# Select their surviving first-stage destination D pins explicitly.
set_max_delay 8 -to [get_pins {mac/tx_fifo/fifo_inst/s_rst_sync2_reg*/D mac/tx_fifo/fifo_inst/m_rst_sync2_reg*/D mac/rx_fifo/fifo_inst/s_rst_sync2_reg*/D mac/rx_fifo/fifo_inst/m_rst_sync2_reg*/D}]
set_false_path -hold -to [get_pins {mac/tx_fifo/fifo_inst/s_rst_sync2_reg*/D mac/tx_fifo/fifo_inst/m_rst_sync2_reg*/D mac/rx_fifo/fifo_inst/s_rst_sync2_reg*/D mac/rx_fifo/fifo_inst/m_rst_sync2_reg*/D}]

# Display mailboxes hold payload through synchronized req/ack; bound only crossing paths.
set_max_delay 10 -to [get_pins {display_cdc/*/req_sync_0_s0/D display_cdc/*/ack_sync_0_s0/D}]
set_false_path -hold -to [get_pins {display_cdc/*/req_sync_0_s0/D display_cdc/*/ack_sync_0_s0/D}]
set_max_delay 20 -from [get_pins {display_cdc/*/held*/Q}] -to [get_pins {display_cdc/*/dst_data*/D}]
set_false_path -hold -from [get_pins {display_cdc/*/held*/Q}] -to [get_pins {display_cdc/*/dst_data*/D}]

# Arora V DDR3 RefDesign 5.8E declares clk/clk_out/memory_clk asynchronous.
# The shipped 60B IP includes calibration/dynamic phase control. Do not apply
# the reference's global clock groups to the surrounding user design. Limit
# the exceptions below to reviewed IP configuration/reset and CDC endpoints.
# Basis and exact vendor/model SHA: docs/TIMING-CLOSURE.md.
# These are PHY initialization/reset controls, not streaming data inputs.
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_rsti_reg_2_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/u_dqs/RESET memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/u_dqs_gen/RESET memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*u_oser8_mem/RESET memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*u_ides8_mem/RESET memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*u_cmd_gen/RESET memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/u_ck_gen/RESET}]
# The same IP reset feeds the four falling-edge RBURST calibration registers.
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_rsti_reg_2_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_init/read_calibration_logic_gen*.rburst_neg*_s0/CLEAR}]
# HOLD = hold_i AND NOT read_rclksel_conf: both are calibration sources.
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_init/read_rclksel_conf_*_s0/Q memory/gw3_top/u_ddr_phy_top/u_ddr_init/hold_gen*.hold_i_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/u_dqs/HOLD}]
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/ides_calib_d_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*u_ides8_mem/CALIB}]
# DLL STEP is a calibrated setting, sampled by enabled clk_out registers;
# it is not a new data word launched at every 400 MHz edge.
set_false_path -through [get_pins {memory/gw3_top/u_ddr_phy_top/u_dll/STEP*}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/dll_step_base_*_s0/D}]
# First stage of a two-flop recalibration synchronizer. Keep the second timed.
set_max_delay 10 -to [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_sync/recalib_s_0_s0/D}]
set_false_path -hold -to [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_sync/recalib_s_0_s0/D}]
# WLOADN transfers the settled initialization state into the reference domain.
set_max_delay 10 -from [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_init_internal_r_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/wloadn_1_s0/D}]
set_false_path -hold -from [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_init_internal_r_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/wloadn_1_s0/D}]

# RTL8211F-CG integrated-delay mode, enabled and read back by a741_phy_config.
# Datasheet rev1.2 Table58: TsetupT/TholdT >=1.2 ns. At the 4 ns DDR
# half-period, data may transition 1.2..2.8 ns after the preceding edge.
# Reserve 0.2 ns additional board skew: input delay 1.0..3.0 ns on both edges.
# This replaces the inherited mixed +2.0/-0.5 provisional no-delay budget.
set_input_delay -clock rgmii_rx_clk -max 3.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -min 1.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -max 3.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -min 1.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
# Gowin 1.9.12.04 resets generated-output-clock latency to zero; its STA
# does not propagate the forwarded ODDR+OBUF path to the capture clock.
# Bound physical output latency here, and REQUIRE the post-route SDF audit
# of all five data/CTL paths against the actual TX clock pad, both corners
# and both edges: |FPGA skew|<=0.3ns (+0.2ns PCB budget => Table58 +/-0.5ns).
# These absolute bounds alone are NOT Ethernet output timing sign-off.
set_max_delay 6.000 -from [get_clocks {tx125m}] -to [get_ports {rgmii_tx_clk rgmii_txd[*] rgmii_tx_ctl}]
set_min_delay 0.500 -from [get_clocks {tx125m}] -to [get_ports {rgmii_tx_clk rgmii_txd[*] rgmii_tx_ctl}]
# Slow MDIO is asynchronous to the FPGA clock. Only its first synchronizer
# stage is excepted; the second stage and the MDC-paced sampling stay timed.
set_false_path -from [get_ports {eth_mdio}] -to [get_pins {phy/bus/mdio_sync_0_s0/D}]

set_max_delay 10.000 -to [get_ports {tft_clk tft_de tft_hsync tft_vsync tft_bl tft_rgb[*]}]
set_false_path -from [get_ports {imu_sda imu_scl}] -to [get_pins {core/sensors/imu_bus/sda_sync_0_s0/D core/sensors/imu_bus/scl_sync_0_s0/D}]
set_false_path -from [get_ports {lidar_rx}] -to [get_pins {core/sensors/lu/sync_0_s0/D}]
