cd [file dirname [file normalize [info script]]]
open_project acg720_right_static.gprj
set_option -top_module acg720_right_static
set_option -output_base_name acg720_right_static
set_option -use_sspi_as_gpio 1
set_option -user_code 0000A71C
set_option -bit_security 0
run all
