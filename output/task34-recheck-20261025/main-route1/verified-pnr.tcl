cd [file dirname [file normalize [info script]]]
open_project a741.gprj
set_option -top_module a741_top
set_option -output_base_name a741
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_cpu_as_gpio 1
set_option -user_code 0000A741
set_option -bit_security 0
set_option -route_option 1
set_option -place_option 1
run pnr
