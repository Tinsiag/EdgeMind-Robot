create_clock -name sys_clk -period 20.000 [get_ports {clk}]
create_clock -name camera_pclk -period 10.000 [get_ports {camera_pclk}]
create_clock -name rgmii_rx_clk -period 8.000 [get_ports {rgmii_rx_clk}]
# Gowin derives PLL output clocks from the PLL primitive automatically.
# External timing numbers are conservative initial budgets, not board measurements.
set_input_delay -clock camera_pclk -max 4.000 [get_ports {camera_data[*] camera_vsync camera_href}]
set_input_delay -clock camera_pclk -min 0.000 [get_ports {camera_data[*] camera_vsync camera_href}]
set_input_delay -clock rgmii_rx_clk -max 2.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -min -0.500 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -max 2.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -min -0.500 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
# Reset and encoder inputs are asynchronous; encoders enter synchronizers.
set_false_path -from [get_ports {stop_n left_enc_a left_enc_b right_enc_a right_enc_b}]
# Keep CDC paths visible in this initial build for explicit report review.
