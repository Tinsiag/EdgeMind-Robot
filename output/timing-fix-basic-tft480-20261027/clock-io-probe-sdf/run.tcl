set_device -name GW5AT-60B GW5AT-LV60PG484AC1/I0
add_file -type verilog {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/gowin_pll.v}
add_file -type verilog {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/gowin_pll_mod.v}
add_file -type verilog {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/pll_init.v}
add_file -type verilog {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/probe.v}
add_file -type cst {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/probe.cst}
add_file -type sdc {C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot/output/timing-fix-basic-tft480-20261027/clock-io-probe-sdf/probe.sdc}
set_option -top_module probe
set_option -output_base_name probe
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_cpu_as_gpio 1
set_option -route_option 1
set_option -place_option 1
set_option -timing_driven 1
set_option -correct_hold_violation 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all


