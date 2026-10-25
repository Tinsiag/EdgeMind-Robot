cd [file dirname [file normalize [info script]]]
open_project unit.gprj
set_option -top_module a741_tft480_panel
set_option -output_base_name tft
set_option -verilog_std sysv2017
run syn
