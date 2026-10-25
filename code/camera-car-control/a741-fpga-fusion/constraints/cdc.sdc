# Only implemented synchronizer inputs are excepted. Never cut whole clock groups.
# Gray pointers are registered; 10 ns bounds skew to the fastest source period.
set_max_delay -to [get_pins {video/*fifo/rg1_*/D video/*fifo/wg1_*/D}] 10
set_false_path -hold -to [get_pins {video/*fifo/rg1_*/D video/*fifo/wg1_*/D}]
# Mailbox request/ack toggles pass two flip-flops before use.
set_max_delay -to [get_pins {video/*/req_sync_0_s0/D video/*/ack_sync_0_s0/D}] 10
set_false_path -hold -to [get_pins {video/*/req_sync_0_s0/D video/*/ack_sync_0_s0/D}]
# Bundled data is held from request through returned acknowledgement.
# Destination capture occurs after two destination sync stages plus detection.
set_max_delay -from [get_pins {video/osd_cdc/held*/Q}] -to [get_pins {video/osd_cdc/dst_data*/D}] 30
set_false_path -hold -from [get_pins {video/osd_cdc/held*/Q}] -to [get_pins {video/osd_cdc/dst_data*/D}]
set_max_delay -from [get_pins {video/diagnostics/held*/Q}] -to [get_pins {video/diagnostics/dst_data*/D}] 20
set_false_path -hold -from [get_pins {video/diagnostics/held*/Q}] -to [get_pins {video/diagnostics/dst_data*/D}]
# Single bit diagnostics cross only through explicit two-stage synchronizers.
set_max_delay -to [get_pins {video/av_pix_0_s0/D video/av_sync_0_s0/D video/er_sync_0_s0/D video/ce_sync_0_s0/D video/co_sync_0_s0/D ddr_ready_sync_0_s0/D camera_ready_sync_0_s0/D phy_ready_rx_0_s0/D phy_ready_tx_0_s0/D}] 10
set_false_path -hold -to [get_pins {video/av_pix_0_s0/D video/av_sync_0_s0/D video/er_sync_0_s0/D video/ce_sync_0_s0/D video/co_sync_0_s0/D ddr_ready_sync_0_s0/D camera_ready_sync_0_s0/D phy_ready_rx_0_s0/D phy_ready_tx_0_s0/D}]
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
