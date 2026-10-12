create_clock -name sys_clk -period 20.000 [get_ports {clk}]
set_false_path -from [get_ports {uart_rx left_enc_a left_enc_b right_enc_a right_enc_b}]
set_false_path -from [get_ports {stop_n}]
