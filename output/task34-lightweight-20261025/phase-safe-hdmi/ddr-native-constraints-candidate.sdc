# Native GW5A DDR3 initialization paths only. Reviewed against the exact
# chapter-38 60B plaintext simulation netlist and Gowin DDR3 RefDesign 5.8E
# 5A25K/5A138K clock-domain exceptions. See ddr-native-review.md.
# The IP's reference-clock reset also holds its UI CLKDIV in reset. The
# serializer reset release is followed by the IP initialization/training
# sequence; it is not a periodic reference-clock to FCLK data transfer.
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/ddr_rsti_reg_2_s0/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/RESET}]
# These DFFs have D=1 and CLEAR=ddr_rst: each changes only once per reset,
# during read calibration. Leave the separate live hold_i path fully timed.
set_false_path -from [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_init/read_rclksel_conf*/Q}] -to [get_pins {memory/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/*/u_dqs/HOLD}]
