cd [file dirname [file normalize [info script]]]
open_project acg720_motor_test_1khz.gprj
set_option -top_module acg720_motor_test_1khz
set_option -output_base_name acg720_motor_test_1khz
set_option -use_sspi_as_gpio 1
set_option -user_code 0000A711
set_option -bit_security 0
run all
