# Run with Gowin gw_sh.exe. Manufacturer sources stay in the local directory.
cd [file dirname [file normalize [info script]]]
open_project .local/ch47/ov5640_ddr3_hdmi.gprj
set_option -top_module gao_ov5640_ddr_hdmi
set_option -output_base_name ov5640_ddr3_hdmi
# The ACG720 board routes two LEDs and the camera SCCB/reset signals to
# GW5AT-60B SSPI dual-purpose pins.  Release those pins as regular IO so the
# 60B package can place the reference board pinout.
set_option -use_sspi_as_gpio 1
run all
