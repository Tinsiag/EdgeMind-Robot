cd [file dirname [file normalize [info script]]]
open_project .local/bist/ddr3_bist.gprj
set_option -top_module ddr3_bist
set_option -output_base_name ddr3_bist
set_option -use_sspi_as_gpio 1
run all
