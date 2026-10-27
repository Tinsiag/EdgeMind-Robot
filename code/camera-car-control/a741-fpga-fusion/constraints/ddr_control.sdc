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
