cd [file dirname [file normalize [info script]]]
open_project experiment.gprj
set_option -top_module telemetry_experiment
set_option -output_base_name telemetry
set_option -verilog_std sysv2017
run syn
