cd [file dirname [file normalize [info script]]]
open_project a745.gprj
set_option -top_module a745_top
set_option -output_base_name a745
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_cpu_as_gpio 1
set_option -user_code 0000A745
set_option -bit_security 0
set_option -route_option 1
set_option -place_option 1
set_option -timing_driven 1
set_option -correct_hold_violation 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
