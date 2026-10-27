create_clock -name sys_clk -period 20 [get_ports {clk50M}]
create_generated_clock -name lcd33m -source [get_ports {clk50M}] -multiply_by 33 -divide_by 50 [get_pins {official/Gowin_PLL/u_pll/PLLA_inst/CLKOUT0}]
set_max_delay 10 -to [get_ports {TFT_rgb[*] TFT_hs TFT_vs TFT_de TFT_pwm}]
