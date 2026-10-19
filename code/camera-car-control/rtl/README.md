# FPGA 集成说明

`camera_ethernet_core.v` 将 A723 运动核心、OV5640 连续采集、EMV1 视频和 EMC1 控制一起接入 RJ45 以太网。摄像头数据经过双时钟 FIFO、RGB565 分包器；控制 UDP 经会话/序号/CRC 校验后桥到内部运动 UART。每帧最后发送 COMMIT 或 ABORT，电脑只显示完整且确认有效的帧。不使用 DDR3，视频拥塞时允许丢帧。视频阻塞不会阻塞运动核心的 PI、TTL 或 STOP；网络控制端点拒绝旧序号和错误 CRC。

`acg720_camera_car_top.v` 是 GW5AT-60B 板级顶层。已接入原厂第59章 PLL、MDIO、RGMII 发送模块，第47章 RGB565 配置表，以及原 DDR3 工程的 SCCB 控制器。编译结果见 [BUILD记录](../BUILD-2026-10-19.md)。

`third_party/verilog-ethernet/manifest.json` 固定了上游 commit 和每个复制文件的 SHA-256；`scripts/prepare_network.py` 可从该 commit 重新准备副本。上游许可证保存在 `third_party/verilog-ethernet/COPYING`。

## 已接入的板级平台

- OV5640 输出800×480 RGB565、高字节先到、VSYNC高消隐。254次寄存器写入、芯片ID与9项关键配置回读成功后才置 `cam_ready`。沿用P7上TY-OV5640模块的自带振荡器，顶层没有输出XCLK。重新初始化时复位整个视频链路。
- RTL8211F RGMII/GMII、MAC FIFO、FCS、MDIO和PLL已接入。RX_CTL按上升沿DV、两边沿异或ER解码，并用Gowin IDDR模型验证字节对齐。PHY沿用地址5和BMCR 0x1200配置，只支持协商为1Gbps，尚未实现100/10Mbps切换。“PHY配置完成”不代表链路已协商成功。
- 每包目的端口 6102，默认 FPGA/PC 地址 192.168.0.2/192.168.0.3。读取 `video_udp_length` 生成 UDP 长度；第一个被接受字节 start=1，最后一个 last=1。默认每包 320 像素加20字节头，即660字节，不要求巨型帧。
- `constraints/acg720_camera_car.cst` 明确全部球号，使用LVCMOS33，并在构建时启用SSPI/CPU管脚复用GPIO。运动和初始化50MHz、网络逻辑PLL50MHz、MAC TX125MHz，RX使用PHY时钟。SDC外部延迟是初始预算；RGMII延迟和实板裕量仍需测量。

控制主链路是 RJ45 UDP：PC `192.168.0.3:5001` → FPGA `192.168.0.2:5000`。`EMC1` 外层含 session、递增 datagram number 和 CRC16，内层原有 `AA 55` UART 帧原样转发到 A723 核心；回复使用相同 session/number。UART/TCP 仍是旧固件调试后备。

网络栈用网关地址判断本地子网，因此网关参数设为LOCAL_IP，使直连PC通过ARP解析，不要求路由器。

| 信号 | FPGA球号 |
| --- | --- |
| 50MHz / S0 stop_n | Y18 / F15 |
| 摄像头 RESET / SCL / SDA | C14 / B13 / D15 |
| 摄像头 PCLK / VSYNC / HREF | B18 / C13 / D14 |
| 摄像头 D0..D7 | C15 B15 B16 D17 C17 E16 D16 B17 |
| RXCLK / RXCTL / RXD0..3 | W19 / AB18 / V17 V18 P19 R19 |
| TXCLK / TXCTL / TXD0..3 | U22 / AA19 / U21 W22 W21 Y22 |
| PHY RESET / MDC / MDIO | V22 / AA18 / W17 |
| 左桥 IN1 / IN2 / ENC A / B | A18 / A19 / A15 / A16 |
| 右桥 IN1 / IN2 / ENC A / B | F13 / F14 / E13 / E14 |

LED0..7为高电平点亮：PLL锁定、摄像头就绪、PHY配置完成、运动已ARM、运动故障、视频坏帧、FIFO曾溢出、初始化错误。D2只表示PHY配置流程完成，不保证链路协商成功；D3亮不代表车轮正在转动。D5下一帧开始清除，D6溢出锁存至复位。正常初始化后未ARM通常D0/D1/D2亮，其余灭，不能以此代替收图或运动验收。

先运行 `scripts/prepare_platform.py` 导入原厂ZIP依赖，再运行 `scripts/build_fpga.py build`。原文件保存在 `.local/platform/original`，适配ROM另存；manifest和provenance记录来源、修改与哈希，不修改原ZIP。未调用Programmer或操作板上SRAM/Flash、电机。
