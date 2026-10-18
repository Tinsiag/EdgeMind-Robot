# A720 上位机运动控制固件，2026-10-17

本机 Gowin V1.9.12.04 从现有工程重新构建，未修改 RTL/CST，未下载到 FPGA。

- 固件：`acg720_motion_control.fs`，User Code `0x0000A720`。
- 器件：GW5AT-60B / GW5AT-LV60PG484AC1/I0。
- SHA256：`544429d865ef759eaf1e35e97f07b9c3a327d74215f0a3dbc078bc0878fed407`。
- 审查：20 个实际端口及方向、LVCMOS33、User Code 通过；50 MHz setup/hold 违例 0/0，Fmax 50.374 MHz。源码哈希与完整结果见 `build-audit.json`。
- 现接线：左 IN1/2=A18/A19，左编码器 A/B=A15/A16；右 IN1/2=F13/F14，右编码器 A/B=E13/E14。

下载时物理断开 VM、车轮架空，Programmer 选择 SRAM Program。下载完成后独立回读 User Code，应为 A720；SRAM 配置掉电丢失。本次未写 Flash，未操作电机。

板载 CH340E 串口为 115200 8N1。先在 VM 断开时运行 host/serial_diagnose.py 确认 3/3 STATUS，预期 DISARMED、faults=0、左右 PWM=0。机械参数复位后丢失，须重新配置；左/右 CPR=1469/1471，当前整数毫米协议轮径=66/66、中心轮距=121。PI 输出上限复位为 1000/1024，试转前须另行设置限幅。烧入后不会自动运行，仍需参数和 ARM/运动命令。

这是已通过构建审查的测试固件，尚无更换驱动后的起动或闭环验收。STOP 为滑行。协议、CLI 和剩余限制见工程 README 与 host/README.md。
