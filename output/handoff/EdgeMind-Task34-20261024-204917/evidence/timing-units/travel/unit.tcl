cd [file dirname [file normalize [info script]]]
open_project unit.gprj
set_option -top_module a741_travel
set_option -output_base_name unit
set_option -verilog_std sysv2017
run syn
