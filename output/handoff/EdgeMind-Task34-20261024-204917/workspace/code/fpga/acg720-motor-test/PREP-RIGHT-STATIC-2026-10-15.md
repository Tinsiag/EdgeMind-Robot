# A71C 右路持续高低电平版，2026-10-15

**已编译、审查、SRAM 下载并独立回读 A71C / 0x70022020。VM 必须保持物理断开。** 用户明确要求 RAIN1 固定为逻辑1、RAIN2固定为逻辑0，无PWM、直接烧录，并确认FPGA已供电、VM未接。

## 固定输出

```verilog
assign right_in1 = 1'b1;
assign right_in2 = 1'b0;
assign left_in1 = 1'b0;
assign left_in2 = 1'b0;
assign camera_reset_n = 1'b0;
```

- RAIN1：F13 / P7-7 / 第4列下 / R-5，配置完成即持续高，标称3.3V逻辑电平。
- RAIN2：F14 / P7-8 / 第4列上 / R-6，持续低。
- 没有按键、初始化等待、PWM、超时或编码器对这两根线的门控；S0也不撤销固定输出。此版用于VM断开时测静态逻辑，不作为带VM的电机试转版。
- 左路两控制脚、相机复位继续保持低。D2常亮、D1常灭；D0显示S0松开，D3/D4显示编码器AB电平或，D5/D6显示S1/S2按下，D7心跳。输入只参与这些显示；S0可清心跳计数，不影响电机控制脚。
- 源码 `rtl/acg720_right_static.v`；工程 `acg720_right_static.gprj`；入口 `build_right_static.tcl`；沿用已确认的新接线CST，未换球号。

## 验证与构建

`acg720_right_static_tb`：配置后立即1/0、S0/S1/S2与四个编码器输入的128种组合、持续多周期观察、停止仿真时钟后仍保持固定电平、左路及相机恒低，全部通过。公共静态管脚回归10项通过。

Gowin V1.9.12于2026-10-15 20:54:26（Asia/Shanghai）完成综合/P&R/位流。实际21端口球号、方向、LVCMOS33、输出驱动/下拉审查通过；50MHz setup/hold违例0/0，Fmax256.533MHz。综合OBUF独立检查：right_in1直接接VCC逻辑常量，right_in2及左路/相机接GND逻辑常量，不是PWM或按键/时限信号。

位流 `impl/pnr/acg720_right_static.fs`，SHA256：

`50FDD181472DE7652F3EC5C8FF7C993CD0DAFB23A87DD95D16D24316FE474DE0`

## 下载与回读

本次下载前实际回读A719。核验器件ID=0x0001481B、USB location=8740和上述位流哈希后，operation_index=2 SRAM Program完成100%，没有写Flash。随后分别operation_index=73/74独立回读User Code=0x0000A71C、Status=0x70022020。当前版本覆盖此前A71A及上轮回读失败状态；掉电后SRAM版会丢失，不能假定下次仍为A71C。

本轮未接VM、未发运动或要求电机试转；未收到A71C下模块引脚实测电压，不能将逻辑常量当作实测3.3V或宣称电机故障已解决。
