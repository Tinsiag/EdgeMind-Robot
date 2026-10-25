
create_clock -name clk400 -period 2.5 -waveform {0 1.25} [get_nets {memory_clk}]
create_clock -name clk100 -period 10 -waveform {0 5} [get_ports {clk}]
create_clock -name sysclk -period 10 -waveform {0 5} [get_pins {u_ddr3/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]
set_clock_groups -asynchronous -group [get_clocks {clk100}] -group [get_clocks {sysclk}]
set_clock_groups -asynchronous -group [get_clocks {sysclk}] -group [get_clocks {clk400}]
set_clock_groups -asynchronous -group [get_clocks {clk100}] -group [get_clocks {clk400}]
