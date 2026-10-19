cd [file dirname [file normalize [info script]]]
open_project camera_car.gprj
set_option -top_module acg720_camera_car_top
set_option -output_base_name camera_car
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_cpu_as_gpio 1
set_option -user_code 0000A740
set_option -bit_security 0
run all
