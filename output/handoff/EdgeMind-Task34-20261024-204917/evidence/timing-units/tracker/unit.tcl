cd [file dirname [file normalize [info script]]]
open_project unit.gprj
set_option -top_module a741_path_tracker
set_option -output_base_name tracker
set_option -verilog_std sysv2017
run syn
