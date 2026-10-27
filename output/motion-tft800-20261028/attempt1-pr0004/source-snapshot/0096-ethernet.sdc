# RTL8211F-CG integrated-delay mode, enabled and read back by a741_phy_config.
# Datasheet rev1.2 Table58: TsetupT/TholdT >=1.2 ns. At the 4 ns DDR
# half-period, data may transition 1.2..2.8 ns after the preceding edge.
# Reserve 0.2 ns additional board skew: input delay 1.0..3.0 ns on both edges.
# This replaces the inherited mixed +2.0/-0.5 provisional no-delay budget.
set_input_delay -clock rgmii_rx_clk -max 3.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -min 1.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -max 3.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
set_input_delay -clock rgmii_rx_clk -clock_fall -add_delay -min 1.000 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]
# Gowin 1.9.12.04 resets generated-output-clock latency to zero; its STA
# does not propagate the forwarded ODDR+OBUF path to the capture clock.
# Bound physical output latency here, and REQUIRE the post-route SDF audit
# of all five data/CTL paths against the actual TX clock pad, both corners
# and both edges: |FPGA skew|<=0.3ns (+0.2ns PCB budget => Table58 +/-0.5ns).
# These absolute bounds alone are NOT Ethernet output timing sign-off.
set_max_delay 6.000 -from [get_clocks {tx125m}] -to [get_ports {rgmii_tx_clk rgmii_txd[*] rgmii_tx_ctl}]
set_min_delay 0.500 -from [get_clocks {tx125m}] -to [get_ports {rgmii_tx_clk rgmii_txd[*] rgmii_tx_ctl}]
# Slow MDIO is asynchronous to the FPGA clock. Only its first synchronizer
# stage is excepted; the second stage and the MDC-paced sampling stay timed.
set_false_path -from [get_ports {eth_mdio}] -to [get_pins {phy/bus/mdio_sync_0_s0/D}]
