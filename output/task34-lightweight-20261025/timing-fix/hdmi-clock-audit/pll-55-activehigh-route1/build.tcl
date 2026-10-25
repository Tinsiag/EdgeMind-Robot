cd [file dirname [file normalize [info script]]]
open_project clock_audit.gprj
set_option -top_module clock_audit
set_option -output_base_name clock_audit
set_option -verilog_std sysv2017
set_option -route_option 1
set_option -place_option 1
run all
