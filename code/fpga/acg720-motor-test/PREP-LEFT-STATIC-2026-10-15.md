# A71D 左路持续高低电平版，2026-10-15

**已编译、审查、SRAM 下载并独立回读 A71D / 0x70022020。当前覆盖 A71C。VM 继续物理断开。**

用户报告“右电机驱动确认烧了”，要求改为 LAIN1 持续高、LAIN2 持续低。右路损坏按用户报告记录，本轮没有独立检查器件损坏或根因；没有改变接线。VM 断开状态沿用上一轮用户明确确认，本轮没有收到新的 VM 状态反馈。

## 固定输出和实际管脚

| 输出 | FPGA 球号 / P7 / 实物接口 | 持续电平 |
| --- | --- | --- |
| LAIN1 | A18 / P7-5 / 第3列下 / L-1 | 1，标称3.3V逻辑高 |
| LAIN2 | A19 / P7-6 / 第3列上 / L-2 | 0 |
| RAIN1 | F13 / P7-7 / R-5 | 0 |
| RAIN2 | F14 / P7-8 / R-6 | 0 |
| camera_reset_n | C14 | 0 |

配置完成立即生效；没有 PWM、按键或超时门控，S0也不改变这五根固定输出。D1常亮、D2常灭。其他输入只参与状态显示，沿用A71C的心跳和原始编码器电平显示，不把D3/D4当作运动判据。此固件用于 VM 断开时检查静态逻辑。

工程 `acg720_left_static.gprj`，顶层 `rtl/acg720_left_static.v`，入口 `build_left_static.tcl`，沿用已确认的公共CST/SDC。旧右路A71C工程和证据保留。

## 验证和下载

- 专用仿真通过：立即1/0、128种按键/编码器输入组合、持续周期及停时钟后输出不变；右路与相机复位始终低。公共管脚静态回归10项通过。
- Gowin V1.9.12于2026-10-15 21:06:15完成构建。实际21端口球号、方向、LVCMOS33及驱动配置通过审查，50MHz setup/hold违例0/0，Fmax256.533MHz。
- 综合网表独立核验：left_in1的OBUF直接接VCC逻辑常量；left_in2、right_in1、right_in2、camera_reset_n的OBUF直接接GND逻辑常量。
- 位流 `impl/pnr/acg720_left_static.fs`，SHA256为 `D332925BC233FD8AFA8D8D5D8B8C8600AB53CE6A46A32487D9A2827C26A06922`。下载前逐一核对位流及构建源文件哈希。
- 下载前回读A71C，器件GW5AT-60B / ID=0x0001481B，USB location8740。仅operation2 SRAM Program，未写Flash；下载后分别operation73/74独立回读A71D / 0x70022020。

本轮未接VM、未获得左路AIN/AOUT新实测值，也没有电机起动验收。源码常量、PNR审查及回读成功不等于实测PAD电压或模块正常。掉电后SRAM版会丢失。

构建/仿真/下载/回读原始日志、实际PNR/STA及综合网表、哈希见 `verification/2026-10-15/left-static-build-program-evidence-20261015.json` 和同目录SHA256SUMS.json。


### 后续实物反馈：两路分别使能、VM均约11V，AOUT仍无输出

**后续用户明确补充：分别在A71C右路、A71D左路测试时，两模块本体VM端均约11V，但两路AOUT均无输出。** 不能再以VM断开或只测了未使能通道解释该结果。两路输出链路异常，重点怀疑驱动模块或底板输出通路；尚无这两次带VM恒定输出测试中模块AIN1/GND、AIN2/GND的实测记录，也未新确认电机插头状态或排除底板短路/钳位，故不把两颗AT8236芯片烧毁作为已证实根因。测试后VM当前通断状态未提供，不再假定仍断开。本次仅记录判断，未改代码、未烧录或操作VM。

证据：both-static-aout-zero-vm-present-user-observation-20261015.json。


## 2026-10-16 重新SRAM下载A71D（最新）

用户明确确认VM已断开、FPGA及下载USB就绪后，重新SRAM下载A71D。下载前实际回读A719，位流及全部构建源文件哈希与2026-10-15归档一致，未改RTL、未重新构建。下载后独立回读A71D / 0x70022020，未写Flash。LAIN1=A18/P7-5/L-1恒高、LAIN2=A19/P7-6/L-2恒低；右路两输入与相机复位恒低。D1常亮、D2灭，无PWM、按键或超时门控，S0不关闭固定输出。VM保持断开；本次没有实际引脚电压或电机起动新反馈。SRAM配置掉电丢失，下次供电须重新确认版本。

证据见motor-test/verification/2026-10-16/left-static-reprogram-evidence-20261016.json。
