create_clock -name sys_clk -period 20 [get_ports {clk}]
set_false_path -from [get_ports {stop_n}]
set_false_path -to [get_pins {*reset*/pipe*/CLEAR}]
report_timing -setup -max_paths 50
report_timing -hold -max_paths 50
report_timing -recovery -max_paths 50
report_timing -removal -max_paths 50
create_generated_clock -name video165m -source [get_ports {clk}] -multiply_by 33 -divide_by 10 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}]
create_generated_clock -name pixel33m -source [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT1}] -master_clock video165m -divide_by 5 [get_pins {pixel_divider/CLKOUT}]
create_generated_clock -name reset33m -source [get_ports {clk}] -multiply_by 33 -divide_by 50 -phase 0 -duty_cycle 50 [get_pins {video_pll/u_pll/PLLA_inst/CLKOUT0}]
set_false_path -to [get_pins {hdmi/serial_reset_pipe*/PRESET}]
