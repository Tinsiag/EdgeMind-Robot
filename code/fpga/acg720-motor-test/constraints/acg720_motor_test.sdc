create_clock -name sys_clk -period 20.000 [get_ports {clk}]
// Asynchronous signals terminate at dedicated first-stage synchronizers.
set_false_path -from [get_ports {left_key_n right_key_n left_enc_a left_enc_b right_enc_a right_enc_b}]
// Raw S0 only asserts reset / kills outputs; release is synchronized.
set_false_path -from [get_ports {stop_n}]
