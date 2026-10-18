cd [file dirname [file normalize [info script]]]
open_project acg720_motion_start50.gprj
set_option -top_module motion_start50_top
set_option -output_base_name acg720_motion_start50
set_option -use_sspi_as_gpio 1
set_option -user_code 0000A721
set_option -bit_security 0
run all
