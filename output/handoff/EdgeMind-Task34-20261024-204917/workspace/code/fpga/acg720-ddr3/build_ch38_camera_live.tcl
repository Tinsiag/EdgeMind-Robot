cd [file dirname [file normalize [info script]]]
open_project .local/framebuffer-first/ch38-camera-live/ch38_camera_live.gprj
set_option -top_module uart_ddr3_tft_hdmi
set_option -output_base_name ch38_camera_live
set_option -use_sspi_as_gpio 1
run all
