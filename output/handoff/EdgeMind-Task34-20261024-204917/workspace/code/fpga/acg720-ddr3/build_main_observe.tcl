# Passive data-flow probes in a copy of the working camera/DDR/HDMI design.
cd [file dirname [file normalize [info script]]]
open_project .local/main-observe/main_observe.gprj
set_option -top_module gao_ov5640_ddr_hdmi
set_option -output_base_name main_observe
set_option -use_sspi_as_gpio 1
run all
