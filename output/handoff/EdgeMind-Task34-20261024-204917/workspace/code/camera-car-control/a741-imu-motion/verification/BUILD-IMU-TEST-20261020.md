# MPU6050接口启用测试版构建

2026-10-20 20:49完成综合、布局布线和位流生成；未自动烧录，未读取实物传感器。

变体：`A741-MPU6050-IMU-TEST-MOTOR-LOCKED`。文件SHA256：`86e7ccfdecc46f352ae22ffe90ca42340ce075558a3fa17bf4a6885adb141589`。输出在独立`.local/gowin-imu-test/`，未覆盖旧诊断输出或A740归档。

## 已完成

- SCL=L18、SDA=M20的100 kHz开漏主I2C接入；探测0x68/0x69、身份校验、配置回读和持续采样。
- XDA=A1、XCL=B2、AD0=M17和INT=B1仅输入，不驱动；ToF/LD06物理管脚不启用。
- 控制器拒绝ARM，顶层四路电机输出固定为0；与上位机配置无关，不能通过hardware_verified绕过。
- 测试模式允许缺少机械轮距时静止校准，不填写虚构轮距；新增C0能力bit6/7与诊断key14～20。
- 上位机新增“IMU诊断”、采样/错误计数和测试模式提示；命令行工具仅STOP、配置、查询及可选校准，不发送ARM或轮速。
- 18组RTL、14项Python回归通过。新测试覆盖0x69地址线级集成、身份/配置/采样/断流失效，以及缺轮距校准、诊断寄存器、ARM拒绝、强制内部驱动下仍无电机输出。

`verification/imu-test-output-audit.json`记录最终综合网表/位流/引脚报告哈希。自动核对四个OBUF的I端恒为GND；SCL/SDA的IOBUF数据输入恒为GND、仅控制输出使能。最终管脚表确认SCL/SDA/AD0在Bank5、XDA/XCL/INT在Bank11，配置均LVCMOS33/3.3 V、无内部上拉。**这些是工具配置，不能作为实际Bank供电测量。**

## 时序未签核

| 项目 | 报告 |
| --- | --- |
| 工具完成 / 源码变化 | compile_passed=true / sources_changed=false |
| 主时钟约束 / 报告Fmax | 50 / 50.475 MHz |
| 显示约束 / 报告Fmax | 33 / 46.720 MHz |
| setup / hold违例端点 | 78 / 35 |
| 最差setup / hold | -1.294 / -1.209 ns |
| 最差recovery / removal | -3.024 / +0.350 ns |
| 最差最小脉宽 | -0.560 ns |
| 逻辑 / BSRAM / DSP | 17882/59904；60/118；25.5/118 |

代表违例在DDR专用PHY/DLL校准、RGMII输入hold、DDR复位/跨域以及时钟脉宽。同步Fmax达到设定目标不等于整板通过，`timing_signed_off=false`。未调整目标频率或扩大整组false path；新增例外仅针对主I2C异步输入进入第一级同步器。

只能作为电机VM断开的、有人监控的陀螺仪实验测试候选，不作为运动/精度验收包。若有视频或网口异常，应连同传感器日志记录，不能断言与剩余时序问题无关。

## 实板待用户执行

用户已报告VCC/SCL/SDA=3.3 V、AD0=3.2 V，预期0x69；本轮没有把其升级为ACK、身份读取或模块健康通过。操作见 [IMU测试步骤](../docs/IMU-TEST.md)。下载新命名位流后，用当前仓库launch.cmd连接，查看ready/valid、样本持续增长与错误稳定，再静止校准并手动转动。

旧错误模块原理图仍撤销；上拉电阻来源、Bank实测/物理针序与全部运动条件未签核。默认sensor-pins.json的outputs_enabled=false仍表示完整传感器启用未获验收；本次显式`--imu-test`的临时接口范围以result.json和实际CST为准。
