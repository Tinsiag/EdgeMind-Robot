cd [file dirname [file normalize [info script]]]
open_project acg720_motor_toggle.gprj
set_option -top_module acg720_motor_toggle
set_option -output_base_name acg720_motor_toggle
set_option -use_sspi_as_gpio 1
set_option -user_code 0000A713
set_option -bit_security 0
run all
