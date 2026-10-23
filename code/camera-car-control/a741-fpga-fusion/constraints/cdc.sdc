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
