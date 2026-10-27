# 480屏基础版时序修正，2026-10-27

范围：布局1、布线1、timing-driven、hold修复；screen-test四个电机输出OBUF接GND。物理实现、离线功能验证和实板验收分别记录。未烧录。

## 原始失败与修正

第一次完整实现见根PNR-20261027.md及output/pnr-basic-tft480-20261027。域内Fmax通过不等于setup/hold/recovery/removal/MPW全部通过。

- TX RAM最小脉宽：Ethernet PLL的750MHz VCO输出分频从6改为3，经专用CLKDIV/2得到125MHz。仅生成副本改变ODIV1_SEL；DDR PLL和加密DDR IP保持原厂字节。移除旧PLL125 BUFG强制约束，自动时钟路由的独立探针未再出现PR1014。
- RGMII RX hold：明确配置并读回RTL8211F page0xd08 reg0x11 bit8与reg0x15 bit3。必须正确读出PHY ID且两项延迟读回成功，才允许MAC接收/发送；错误锁存直到复位。保留10ms复位、20ms等待和2kHz MDC。
- RX五根数据/控制信号添加IODELAY64，默认参数0使共用模块的其他工程行为不变。IODELAY名义12.5ps/tap仅供结构理解，签核使用器件时序模型。

## Ethernet外部预算

实物原理图U11为RTL8211F-CG，PHY地址5。源资料在output/task34-resume-20261024/tool-docs/rtl8211f-rev12.pdf；寄存器定义交叉核对Linux v6.12 drivers/net/phy/realtek.c，下载记录在本轮输出目录。没有使用RTL8211F-M8替代CG时序。

Table58集成延迟的发送端setup/hold最小1.2ns，8ns周期双沿意味着数据相对前一边沿在1.2..2.8ns变化；加入0.2ns板级偏斜预算后，RX两沿约束为1.0..3.0ns。FPGA TX边沿与转发时钟名义同相，PHY内部延迟开启；两沿输出预算要求FPGA处偏斜在±0.3ns内，留0.2ns板级偏斜以满足无延迟发送端±0.5ns规范。

实测工具行为：在TX输出端建立generated clock时，1.9.12.04报告的capture clock path为零，没有传播ODDR及OBUF的实际延迟（attempt-03）。不能用零延迟参考得到的-4ns左右余量来判断输出偏斜。现对六个TX输出施加0.5..6ns绝对路径预算，并导出同一次实现的SDF和明文网表，必须另行核对所有数据/CTL与时钟输出的物理路径差，覆盖快慢模型和升降沿。绝对预算通过不等于TX接口签核；只有相对偏斜审查也通过才可交付。

0.2ns是板级设计预算，未经示波器测量。正常网络使用当前MAC支持的1Gbps链路；本轮不增加10/100M速率自适应。MDIO两级同步器仅首级异步输入例外，读事务有固定64位上限，错误不自动重试。

## DDR控制例外的依据与边界

Gowin DDR3 RefDesign 5.8E压缩包SHA256：39d0d30584a7c1740d5921c1d7934b334f5fc2db7909d99e4283a25e9a75cc03。其Arora V 25K/138K的SDC均将50MHz参考、400MHz memory与100MHz UI三者逐对声明异步。IPUG281-2.6E §4.4.2/4.4.3说明HCLK/PCLK和动态PLL控制，并要求rst_n相对参考时钟同步释放。本顶层保留该接法及PLL_LOCK直连。

上述参考不是60B整板的直接签核。为避免全局切断用户数据路径，检查了板卡第38章同一IP的明文仿真网表：board-60b-ddr3-memory-interface.vo，SHA256 c9da2a7b0f89226a6063b3d57037f6ed3d36ca2a0914de2eaefe7bf22a119cbd，已和原zip逐字节核对。仅适配以下端点：

| 源→目的 | 结构及处理 |
| --- | --- |
| ddr_rsti_reg_2/Q→62个wds下RESET及4个RBURST校准寄存器CLEAR | 参考域产生的IP全局初始化复位，仅切对应硬核/串并转换原语RESET与已核对的四个下降沿校准寄存器复位；用户UI复位另有同步器。 |
| read_rclksel_conf/Q、hold_i/Q→两个DQS/HOLD | 网表中HOLD=hold_i AND NOT read_rclksel_conf，两者均为UI校准配置；不把运行时DQ/DQS数据切掉。 |
| ides_calib_d/Q→16个IDES8_MEM/CALIB | 厂商校准脉冲进入高速原语；保留数据、地址及其余控制检查。 |
| through DDRDLL/STEP→dll_step_base/D | DLL校准结果，由UI使能寄存器采样；不是每个400MHz边沿发出的新数据字。用through覆盖工具从CLKIN起算、经过STEP的原语路径。 |
| sys_reset→recalib_s_0/D | 参考域两级同步器首级；max10ns并仅切hold，第二级保持正常时序。 |
| ddr_init_internal_r/Q→wloadn_1/D | 厂商初始化完成电平跨到参考域；max10ns并仅切hold，保持其他路径。 |

这些约束是对官方异步控制模型的局部适配，不是逻辑功能修复，也不证明DDR板级信号完整性。每次实现须确认选择器确实命中预期原语、全部约束生效，以及剩余数据/控制路径正常计时；不能看到其他违例便扩大例外。实板还须确认校准完成、连续摄像头读写与画面稳定。

## 验证

phy_config_tb使用引脚级Clause22模型，覆盖完整12事务、RMW保留无关位、缺ACK、ID错误、TX/RX/BMCR读回错误、中途复位；响应延迟按Table57上限300ns建模。ethernet_io_tb使用安装版本GW5A原语，验证CLKDIV频率/占空比/复位与IODELAY+IDDR字节、DV、ER对齐。完整回归与最终物理报告以本轮output/timing-fix-basic-tft480-20261027保存的实际结果为准，独立探针不作为整板验收。
