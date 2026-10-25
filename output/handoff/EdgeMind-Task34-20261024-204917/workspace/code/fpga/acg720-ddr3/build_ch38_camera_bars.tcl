cd [file dirname [file normalize [info script]]]
open_project .local/framebuffer-first/ch38-camera-bars/ch38_camera_bars.gprj
set_option -top_module uart_ddr3_tft_hdmi
set_option -output_base_name ch38_camera_bars
set_option -use_sspi_as_gpio 1
run all
