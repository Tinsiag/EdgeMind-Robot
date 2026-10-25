cd [file dirname [file normalize [info script]]]
open_project acg720_motion_sync.gprj
set_option -top_module motion_sync_top
set_option -output_base_name acg720_motion_sync
set_option -use_sspi_as_gpio 1
set_option -user_code 0000A723
set_option -bit_security 0
run all
