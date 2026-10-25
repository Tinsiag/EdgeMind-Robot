# Isolated chapter 38, one complete frame through both official FIFOs and DDR.
cd [file dirname [file normalize [info script]]]
open_project .local/framebuffer-first/ch38-frame-test/ch38_frame_test.gprj
set_option -top_module uart_ddr3_tft_hdmi
set_option -output_base_name ch38_frame_test
set_option -use_sspi_as_gpio 1
run all
