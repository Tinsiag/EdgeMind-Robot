//Copyright (C)2014-2025 GOWIN Semiconductor Corporation.
//All rights reserved.
//File Title: Timing Constraints file
//Tool Version: V1.9.11.01 (64-bit) 
//Created Time: 2025-02-13 13:58:36
create_clock -name clk_in_osc_50 -period 20 -waveform {0 10} [get_ports {clk}]
create_clock -name memory_clk -period 5 -waveform {0 2.5} [get_pins {pll/rpll_inst/CLKOUT}]
create_generated_clock -name clk_user -source [get_pins {pll/rpll_inst/CLKOUT}] -master_clock memory_clk -divide_by 2 [get_pins {u_ddr3/u_gw3_phy_mc/u_ddr_phy_top/fclkdiv/CLKOUT}]
set_clock_groups -asynchronous -group [get_clocks {clk_in_osc_50}] -group [get_clocks {memory_clk clk_user}]
set_clock_groups -asynchronous -group [get_clocks {memory_clk}] -group [get_clocks {clk_user}]
