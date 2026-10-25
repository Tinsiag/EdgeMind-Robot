
create_clock -name clk4x -period 2.5 -waveform {0 1.25} [get_pins {Gowin_PLL_inst/PLLA_inst/CLKOUT2}]
create_clock -name clk1x -period 10 -waveform {0 5} [get_pins {u_ddr3/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]
create_clock -name clkin -period 20 -waveform {0 10} [get_ports {clk_g}]
set_clock_groups -asynchronous -group [get_clocks {clkin}] -group [get_clocks {clk4x}]
set_clock_groups -asynchronous -group [get_clocks {clk4x}] -group [get_clocks {clk1x}]
set_clock_groups -asynchronous -group [get_clocks {clkin}] -group [get_clocks {clk1x}]
