create_clock -name sys_clk -period 20 [get_ports {clk}]
set_false_path -from [get_ports {stop_n}]
set_false_path -to [get_pins {*reset*/pipe*/CLEAR}]
report_timing -setup -max_paths 50
report_timing -hold -max_paths 50
report_timing -recovery -max_paths 50
report_timing -removal -max_paths 50
