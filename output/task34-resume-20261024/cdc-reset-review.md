# MAC FIFO reset CDC review (pending routed confirmation)

The reused verilog-ethernet axis_async_fifo.v lines 355-380 implement cross-domain reset status as follows:

- s_rst_sync1_reg is registered on m_clk; s_rst_sync2_reg is its first s_clk sampling stage, followed by s_rst_sync3_reg.
- m_rst_sync1_reg is registered on s_clk; m_rst_sync2_reg is its first m_clk sampling stage, followed by m_rst_sync3_reg.

A maximum 8 ns budget and hold exception are applied to the first-destination-D pins of these four explicit pairs in mac/tx_fifo and mac/rx_fifo. Later synchronizer stages and reset consumers remain timed. The exception must be verified as resolving in the routed report. No DDR calibration or reset exception is inferred from this unrelated MAC review.

The constraints now select destination D pins because synthesis shares some source reset registers across FIFOs. The first explicit source list was rejected by Gowin TA2003; this rejection is archived in pnr-constraint-rejected. The surviving destination selectors passed timing-constraint parsing. Routed timing remains pending; this note does not sign off timing.
