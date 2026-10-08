cd [file dirname [file normalize [info script]]]
open_project .local/camera-ddr/camera_ddr_fifo_bist_b21.gprj
set_option -top_module camera_ddr_fifo_bist
set_option -output_base_name camera_ddr_fifo_bist_b21
set_option -use_sspi_as_gpio 1
run all
