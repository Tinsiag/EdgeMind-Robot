# EdgeMind-Robot

当前工程是 [A745 片上自主避障](code/camera-car-control/a745-autonomous/README.md)。上电未 ARM，S1 本地启停，网口只发送遥测。摄像头初始化与采集、应用控制、网络发送和文字界面已重构。

- 使用与接线：[A745 说明](code/camera-car-control/a745-autonomous/README.md)。
- 当前状态、位流和烧录证据：[最新交接](HANDOFF-20261031.md)。
- 后续接手：[提示词](NEXT-AI-PROMPT-20261031.md)。
- 电脑只读遥测：`code/camera-car-control/launch.cmd`。
- 机械设计：`model/chassis/v5-rgb-touch-display/`；电源板：`pcb/power/`；当前接线依据：`doc/电机/实物接线更正_2026-10-15.md`。

旧固件把电机输出锁为低电平的限制已在 A745 解除。这是内部逻辑锁，不是拆除公共地的指令。左轮 LAIN1/2 对应 FPGA A18/A19，右轮 RAIN1/2 对应 F13/F14；FPGA 与驱动板保持公共 GND。

项目清理已完成，删除18,685个旧文件，约15.92GB，当前源码和硬件设计保留。详见[清理记录](PROJECT-CLEANUP.md)。

用户已授权本次交接提交、推送 GitHub，并同步清理远端 main 当前目录；不关机。重新加载后的显示、真正断电冷启动、轮子运动和落地避障分别验收，具体结论见交接。

当前固化FW74504，真实冷启动已通过；用户确认能前进，但转弯仍停在BLOCK，尚未验收。可重用固化文件见[当前发布位流](output/releases/fw74504/manifest.json)，完整交接见[接手文档](.agent/main/handoff.md)。
