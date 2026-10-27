# 480屏基础版修正与复验完成

2026-10-27 23:28。当前**离线检查通过，可准备四路电机硬锁版本的实板试屏**。未烧录，未ARM，未运行电机，未上传GitHub；Flash固化和断电重启尚未验证。

当前入口：[STATUS.json](output/timing-fix-basic-tft480-20261027/STATUS.json)。这次结论只对应下面的准确位流，不能套用到正常运动版本或此前失败的位流。

## 检查结果

| 项目 | 本次结果 |
| --- | --- |
| RTL回归 | 37项通过，包括官方480屏逐采样等价、摄像头/DDR/TFT链路、IMU、LD06方向、安全停止、软核与网口 |
| Python回归 | 41项通过 |
| 最终setup余量 | +1.019 ns |
| 最终hold余量 | +0.041 ns |
| 最终recovery余量 | +3.465 ns |
| 最终removal余量 | +0.350 ns |
| 最小脉宽余量 | +1.122 ns |
| 工具报告违例 | setup类0、hold类0；全部7个有效时钟定义匹配，约束均Actived |
| TX实际输出偏斜 | 最大绝对值0.022 ns；计入0.2ns板级预算和0.035ns余量后，剩余0.243 ns |
| 电机物理输出 | left/right四个OBUF输入均为GND |
| 布局/布线 | 1/1，timing-driven、hold修复开启 |
| CLS / BSRAM / DSP | 17809/29952（60%）/ 60/118（51%）/ 24/118（21%） |
| 耗时 | 最终PNR驱动291.452秒，复用哈希核对过的综合结果；工具分项布局156秒、布线100秒 |
| 最终PNR警告/错误 | 均无；综合仍有历史接口宽度、未使用输出等警告，不能称整个流程零警告 |

系统50MHz域Fmax56.736MHz、摄像头100MHz域111.350MHz、RX125MHz域170.710MHz、TX125MHz域191.303MHz。Fmax只作域内补充依据，上表覆盖其他时序类型。

## 修改内容与适用边界

1. Ethernet PLL输出改成250MHz，经专用CLKDIV/2生成125MHz，解决原TX FIFO RAM最小脉宽问题；移除旧强制BUFG约束，最终pll125仍使用PRIMARY时钟路径。
2. 新增RTL8211F引脚级MDIO配置：核对PHY ID、读改写及读回RX/TX延迟位，失败不开放MAC。RX五根数据/控制输入各使用IODELAY64；另一工程默认参数0保持原行为。
3. DDR依据厂商参考及匹配的60B原始网表，逐项约束校准、初始化复位和CDC首级。没有全局切断时钟域，DDR加密IP/PLL保持原厂字节。此部分是时序模型适配，不能替代实板校准与持续读写验证。
4. 工具对输出generated clock未传播ODDR/OBUF延迟，因此TX接口采用绝对路径预算加同一次布线SDF的引脚偏斜审查，覆盖三个PVT角和四种时钟/数据边沿组合。0.2ns板级偏斜是预算，尚未实测；MAC仍按1Gbps使用。

具体推导：[TIMING-CLOSURE.md](code/camera-car-control/a741-fpga-fusion/docs/TIMING-CLOSURE.md)。480×272、5MHz、525×286、DE(42,11)和J1接线不变。

## 准备烧录

固定归档位流：`output/timing-fix-basic-tft480-20261027/build-evidence-final/a741.fs`

SHA-256：`094862d12885cd786f3d5efb676205a9a999ff64e244b533e72ef538b4b2c8ee`

烧录工具仅进行了无硬件预览，见[FLASH-PREVIEW.txt](output/timing-fix-basic-tft480-20261027/FLASH-PREVIEW.txt)。实际执行仍用`scripts/fpga/program_flash.py`，外部SPI Flash操作54、地址0，写入校验后Reprogram，不使用SRAM替代。

现在可以给FPGA、480屏和下载器上电，电机VM保持关闭。按根AGENTS.md，烧录前需要用户确认当时VM关闭和板卡就绪。烧录成功后分别检查屏幕、摄像头连续画面、DDR校准、IMU文字、网口设置/调试，最后断开可能反向供电的连接并实际断电重启。此位流保持四路电机输出接地，运动验收不在此次实板试屏范围内。

## 证据链

- [最终时序审查](output/timing-fix-basic-tft480-20261027/TIMING-REVIEW.json)、[TX偏斜审查](output/timing-fix-basic-tft480-20261027/TX-SKEW-REVIEW.json)、[实际原语端点](output/timing-fix-basic-tft480-20261027/CONSTRAINT-TARGETS.json)。
- [输入及综合复用核对](output/timing-fix-basic-tft480-20261027/VALIDATION-CHAIN.json)、[物理资源/管脚/电机锁](output/timing-fix-basic-tft480-20261027/PHYSICAL-REVIEW.json)、[归档哈希](output/timing-fix-basic-tft480-20261027/ARTIFACT-SHA256.json)。
- 最终完整证据在`build-evidence-final/`。最初综合已完成，其后的两次约束解析失败记录在`attempt-01-constraint-error/`和`attempt-02-constraint-error/`；中间一次时序失败在`attempt-03/`。不得把这些中间位流当作最终交付。
- 输出目录中的旧`build-evidence/`是中途归档工作区，后续复制因只读属性中止，内容不作为一致快照使用；原中间版本完整快照在`attempt-03/build-evidence/`。

离线复核命令：使用项目venv Python依次运行本轮目录的`inspect_implementation.py`、`audit_constraint_targets.py`、`audit_tx_sdf.py`、`finalize_review.py`。最后一步核对当前源码、回归、综合及最终位流一致后发布STATUS；不操作硬件。
