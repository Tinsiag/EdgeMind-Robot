# Board timing review (not sign-off)

The ACG720 138K/60K common schematic, sheet 6, identifies U11 as RTL8211F-CG. R43 and R44 pull RXD0/RXDLY and RXD1/TXDLY high through 4.7 kohm to VCC3V3. The compiled original chapter-59 PHY sequence only writes BMCR 0x1200 and reads it back; it does not override these delay straps. This is schematic evidence, not measurement of the assembled board.

The inherited RGMII input constraints (+2.0 ns max / -0.5 ns min on both edges) are explicitly provisional. They must be reconciled with the RTL8211F enabled internal-delay timing specification and PCB trace skew before final I/O sign-off; they are not being widened to hide hold failures.

Gowin SUG1541 section 2.8 documents CLOCK_LOC with BUFG routing, and UG306 describes low-skew global clocks. Historical 2026-10-23 MPW failures at hdmi/serial_reset (165 MHz) and MAC TX FIFO RAM (125 MHz) require checking the new routed result and actual clock routing. Their old numbers are not this build's validation.

Source schematic: C:\Users\sc\Documents\Dev\Hardware\fpga\小梅哥ACG720国产高云FPGA教学开发板资料\06_硬件图纸\ACG720-138&60K通用原理图.pdf

SHA-256: 47e4b849edc46ab16925aaa3d61b7bb4e766b24222a1dabf0b7ec3bf9ae3c9f4

The exact chapter-38 and chapter-47 archives recorded in platform-tft480/provenance.json were inspected. Neither archive contains an SDC file; chapter 38's project lists the encrypted DDR module and physical constraints but no timing-constraint source. This does not justify excluding DDR calibration, reset recovery, or external DDR timing from sign-off. Their generated-clock and dynamic-phase assumptions still need explicit review against the routed report and the matching vendor IP documentation.
