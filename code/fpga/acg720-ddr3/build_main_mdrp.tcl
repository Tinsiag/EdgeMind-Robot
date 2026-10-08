# Main pipeline with passive probes and the documented PLL mDRP handoff.
cd [file dirname [file normalize [info script]]]
open_project .local/main-mdrp/main_mdrp.gprj
set_option -top_module gao_ov5640_ddr_hdmi
set_option -output_base_name main_mdrp
set_option -use_sspi_as_gpio 1
run all
